import os
from ast import literal_eval
from uuid import uuid4

from django.contrib import auth, messages
from django.contrib.auth.models import User
from django.http import (Http404, HttpResponseForbidden,
                         HttpResponsePermanentRedirect, HttpResponseRedirect)
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import ugettext as _
from django.views.decorators.http import (require_GET, require_http_methods,
                                          require_POST)
# from axes.decorators import watch_login
from django_statsd.clients import statsd
from mozilla_django_oidc.views import (OIDCAuthenticationRequestView,
                                       OIDCLogoutView)
from tidings.models import Watch

from kitsune import users as constants
from kitsune.access.decorators import (login_required, logout_required,
                                       permission_required)
from kitsune.kbadge.models import Award
from kitsune.questions.utils import (mark_content_as_spam, num_answers,
                                     num_questions, num_solutions)
from kitsune.sumo.decorators import ssl_required
from kitsune.sumo.templatetags.jinja_helpers import urlparams
from kitsune.sumo.urlresolvers import reverse
from kitsune.sumo.utils import get_next_url, simple_paginate
from kitsune.upload.tasks import _create_image_thumbnail
from kitsune.users.forms import AvatarForm, ProfileForm, SettingsForm
from kitsune.users.models import Deactivation, Profile
from kitsune.users.templatetags.jinja_helpers import profile_url
from kitsune.users.utils import (add_to_contributors, deactivate_user,
                                 get_oidc_fxa_setting)
from kitsune.wiki.models import (user_documents, user_num_documents,
                                 user_redirects)


@ssl_required
@logout_required
@require_http_methods(['GET', 'POST'])
def user_auth(request, notification=None):
    """
    Show user authorization page which includes a link for
    FXA sign-up/login and the legacy login form
    """
    next_url = get_next_url(request) or reverse('home')

    return render(request, 'users/auth.html', {
        'next_url': next_url,
        'notification': notification
    })


@ssl_required
def login(request):
    """
    Legacy view for logging in SUMO users. This is being deprecated
    in favor of FXA login.
    """
    if request.method == 'GET':
        url = reverse('users.auth') + '?' + request.GET.urlencode()
        return HttpResponsePermanentRedirect(url)

    if request.user.is_authenticated():
        # We re-direct to the profile screen
        profile_url = urlparams(
            reverse('users.profile', args=[request.user.username]),
            fpa=1,
        )
        res = HttpResponseRedirect(profile_url)
        max_age = (None if settings.SESSION_EXPIRE_AT_BROWSER_CLOSE
                   else settings.SESSION_COOKIE_AGE)
        res.set_cookie(settings.SESSION_EXISTS_COOKIE,
                       '1',
                       secure=False,
                       max_age=max_age)
        return res

    return user_auth(request)


@ssl_required
@require_POST
def logout(request):
    """Log the user out."""
    auth.logout(request)
    statsd.incr('user.logout')

    return HttpResponseRedirect(get_next_url(request) or reverse('home'))


@require_GET
def profile(request, username):
    # The browser replaces '+' in URL's with ' ' but since we never have ' ' in
    # URL's we can assume everytime we see ' ' it was a '+' that was replaced.
    # We do this to deal with legacy usernames that have a '+' in them.
    username = username.replace(' ', '+')

    user = User.objects.filter(username=username).first()

    if not user:
        try:
            user = get_object_or_404(User, id=username)
        except ValueError:
            raise Http404('No Profile matches the given query.')
        return redirect(reverse('users.profile', args=(user.username,)))

    user_profile = get_object_or_404(Profile, user__id=user.id)

    if not (request.user.has_perm('users.deactivate_users') or
            user_profile.user.is_active):
        raise Http404('No Profile matches the given query.')

    groups = user_profile.user.groups.all()
    return render(request, 'users/profile.html', {
        'profile': user_profile,
        'awards': Award.objects.filter(user=user_profile.user),
        'groups': groups,
        'num_questions': num_questions(user_profile.user),
        'num_answers': num_answers(user_profile.user),
        'num_solutions': num_solutions(user_profile.user),
        'num_documents': user_num_documents(user_profile.user)})


@login_required
@require_POST
def close_account(request):
    # Clear the profile
    user_id = request.user.id
    profile = get_object_or_404(Profile, user__id=user_id)
    profile.clear()
    profile.fxa_uid = '{user_id}-{uid}'.format(user_id=user_id, uid=str(uuid4()))
    profile.save()

    # Deactivate the user and change key information
    request.user.username = 'user%s' % user_id
    request.user.email = '%s@example.com' % user_id
    request.user.is_active = False

    # Remove from all groups
    request.user.groups.clear()

    request.user.save()

    # Log the user out
    auth.logout(request)

    return render(request, 'users/close_account.html')


@require_POST
@permission_required('users.deactivate_users')
def deactivate(request, mark_spam=False):
    user = get_object_or_404(User, id=request.POST['user_id'], is_active=True)
    deactivate_user(user, request.user)

    if mark_spam:
        mark_content_as_spam(user, request.user)

    return HttpResponseRedirect(profile_url(user))


@require_GET
@permission_required('users.deactivate_users')
def deactivation_log(request):
    deactivations_qs = Deactivation.objects.order_by('-date')
    deactivations = simple_paginate(request, deactivations_qs,
                                    per_page=constants.DEACTIVATIONS_PER_PAGE)
    return render(request, 'users/deactivation_log.html', {
        'deactivations': deactivations})


@require_GET
def documents_contributed(request, username):
    user_profile = get_object_or_404(
        Profile, user__username=username, user__is_active=True)

    return render(request, 'users/documents_contributed.html', {
        'profile': user_profile,
        'documents': user_documents(user_profile.user),
        'redirects': user_redirects(user_profile.user)})


@login_required
@require_http_methods(['GET', 'POST'])
def edit_settings(request):
    """Edit user settings"""
    template = 'users/edit_settings.html'
    if request.method == 'POST':
        form = SettingsForm(request.POST)
        if form.is_valid():
            form.save_for_user(request.user)
            messages.add_message(request, messages.INFO,
                                 _(u'Your settings have been saved.'))
            return HttpResponseRedirect(reverse('users.edit_settings'))
        # Invalid form
        return render(request, template, {'form': form})

    # Pass the current user's settings as the initial values.
    values = request.user.settings.values()
    initial = dict()
    for v in values:
        try:
            # Uses ast.literal_eval to convert 'False' => False etc.
            # TODO: Make more resilient.
            initial[v['name']] = literal_eval(v['value'])
        except (SyntaxError, ValueError):
            # Attempted to convert the string value to a Python value
            # but failed so leave it a string.
            initial[v['name']] = v['value']
    form = SettingsForm(initial=initial)
    return render(request, template, {'form': form})


@login_required
@require_http_methods(['GET', 'POST'])
def edit_watch_list(request):
    """Edit watch list"""
    watches = Watch.objects.filter(user=request.user).order_by('content_type')

    watch_list = []
    for w in watches:
        if w.content_object is not None:
            if w.content_type.name == 'question':
                # Only list questions that are not archived
                if not w.content_object.is_archived:
                    watch_list.append(w)
            else:
                watch_list.append(w)

    if request.method == 'POST':
        for w in watch_list:
            w.is_active = 'watch_%s' % w.id in request.POST
            w.save()

    return render(request, 'users/edit_watches.html', {
        'watch_list': watch_list})


@login_required
@require_http_methods(['GET', 'POST'])
def edit_profile(request, username=None):
    """Edit user profile."""
    # If a username is specified, we are editing somebody else's profile.
    if username is not None and username != request.user.username:
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            raise Http404

        # Make sure the auth'd user has permission:
        if not request.user.has_perm('users.change_profile'):
            return HttpResponseForbidden()
    else:
        user = request.user

    try:
        user_profile = Profile.objects.get(user=user)
    except Profile.DoesNotExist:
        # TODO: Once we do user profile migrations, all users should have a
        # a profile. We can remove this fallback.
        user_profile = Profile.objects.create(user=user)

    if request.method == 'POST':
        form = ProfileForm(request.POST, request.FILES, instance=user_profile)
        if form.is_valid():
            user_profile = form.save()
            new_timezone = user_profile.timezone
            tz_changed = request.session.get('timezone', None) != new_timezone
            if tz_changed and user == request.user:
                request.session['timezone'] = new_timezone
            return HttpResponseRedirect(reverse('users.profile',
                                                args=[user.username]))
    else:  # request.method == 'GET'
        form = ProfileForm(instance=user_profile)

    # TODO: detect timezone automatically from client side, see
    # http://rocketscience.itteco.org/2010/03/13/automatic-users-timezone-determination-with-javascript-and-django-timezones/  # noqa
    msgs = messages.get_messages(request)
    fxa_messages = [
        m.message for m in msgs if m.message.startswith('fxa_notification')
    ]

    return render(request, 'users/edit_profile.html', {
        'form': form, 'profile': user_profile, 'fxa_messages': fxa_messages})


@login_required
@require_http_methods(['POST'])
def make_contributor(request):
    """Adds the logged in user to the contributor group"""
    add_to_contributors(request.user, request.LANGUAGE_CODE)

    if 'return_to' in request.POST:
        return HttpResponseRedirect(request.POST['return_to'])
    else:
        return HttpResponseRedirect(reverse('landings.get_involved'))


@login_required
@require_http_methods(['GET', 'POST'])
def edit_avatar(request):
    """Edit user avatar."""
    try:
        user_profile = Profile.objects.get(user=request.user)
    except Profile.DoesNotExist:
        # TODO: Once we do user profile migrations, all users should have a
        # a profile. We can remove this fallback.
        user_profile = Profile.objects.create(user=request.user)

    if user_profile.is_fxa_migrated:
        raise Http404

    if request.method == 'POST':
        # Upload new avatar and replace old one.
        old_avatar_path = None
        if user_profile.avatar and os.path.isfile(user_profile.avatar.path):
            # Need to store the path, not the file here, or else django's
            # form.is_valid() messes with it.
            old_avatar_path = user_profile.avatar.path
        form = AvatarForm(request.POST, request.FILES, instance=user_profile)
        if form.is_valid():
            if old_avatar_path:
                os.unlink(old_avatar_path)
            user_profile = form.save()

            content = _create_image_thumbnail(user_profile.avatar.path,
                                              settings.AVATAR_SIZE, pad=True)
            # We want everything as .png
            name = user_profile.avatar.name + ".png"
            # Delete uploaded avatar and replace with thumbnail.
            user_profile.avatar.delete()
            user_profile.avatar.save(name, content, save=True)
            return HttpResponseRedirect(reverse('users.edit_my_profile'))

    else:  # request.method == 'GET'
        form = AvatarForm(instance=user_profile)

    return render(request, 'users/edit_avatar.html', {
        'form': form, 'profile': user_profile})


@login_required
@require_http_methods(['GET', 'POST'])
def delete_avatar(request):
    """Delete user avatar."""
    try:
        user_profile = Profile.objects.get(user=request.user)
    except Profile.DoesNotExist:
        # TODO: Once we do user profile migrations, all users should have a
        # a profile. We can remove this fallback.
        user_profile = Profile.objects.create(user=request.user)

    if user_profile.is_fxa_migrated:
        raise Http404

    if request.method == 'POST':
        # Delete avatar here
        if user_profile.avatar:
            user_profile.avatar.delete()
        return HttpResponseRedirect(reverse('users.edit_my_profile'))
    # else:  # request.method == 'GET'

    return render(request, 'users/confirm_avatar_delete.html', {
        'profile': user_profile})


class FXAAuthenticateView(OIDCAuthenticationRequestView):

    @staticmethod
    def get_settings(attr, *args):
        """Override settings for Firefox Accounts.

        The default values for the OIDC lib are used for the SSO login in the admin
        interface. For Firefox Accounts we need to pass different values, pointing to the
        correct endpoints and RP specific attributes.
        """

        val = get_oidc_fxa_setting(attr)
        if val is not None:
            return val
        return super(FXAAuthenticateView, FXAAuthenticateView).get_settings(attr, *args)

    def get(self, request):
        is_contributor = request.GET.get('is_contributor') == 'True'
        request.session['is_contributor'] = is_contributor
        return super(FXAAuthenticateView, self).get(request)


class FXALogoutView(OIDCLogoutView):

    @staticmethod
    def get_settings(attr, *args):
        """Override the logout url for Firefox Accounts."""

        val = get_oidc_fxa_setting(attr)
        if val is not None:
            return val
        return super(FXALogoutView, FXALogoutView).get_settings(attr, *args)
