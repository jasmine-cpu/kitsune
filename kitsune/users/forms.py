import re
from datetime import datetime

from django import forms
from django.conf import settings
from django.core.cache import cache
from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_lazy as _lazy

from kitsune.sumo.widgets import ImageWidget
from kitsune.upload.forms import LimitedImageField
from kitsune.upload.utils import FileTooLargeError, check_file_size
from kitsune.users.models import Profile
from kitsune.users.widgets import FacebookURLWidget, MonthYearWidget

USERNAME_INVALID = _lazy(
    u"Username may contain only English letters, " "numbers and ./-/_ characters."
)
USERNAME_REQUIRED = _lazy(u"Username is required.")
USERNAME_SHORT = _lazy(
    u"Username is too short (%(show_value)s characters). "
    "It must be at least %(limit_value)s characters."
)
USERNAME_LONG = _lazy(
    u"Username is too long (%(show_value)s characters). "
    "It must be %(limit_value)s characters or less."
)
EMAIL_REQUIRED = _lazy(u"Email address is required.")
EMAIL_SHORT = _lazy(
    u"Email address is too short (%(show_value)s characters). "
    "It must be at least %(limit_value)s characters."
)
EMAIL_LONG = _lazy(
    u"Email address is too long (%(show_value)s characters). "
    "It must be %(limit_value)s characters or less."
)
PASSWD_REQUIRED = _lazy(u"Password is required.")
PASSWD2_REQUIRED = _lazy(u"Please enter your password twice.")
PASSWD_MIN_LENGTH = 8
PASSWD_MIN_LENGTH_MSG = _lazy("Password must be 8 or more characters.")

# Enforces at least one digit and at least one alpha character.
password_re = re.compile(r"(?=.*\d)(?=.*[a-zA-Z])")


class SettingsForm(forms.Form):
    forums_watch_new_thread = forms.BooleanField(
        required=False, initial=True, label=_lazy(u"Watch forum threads I start")
    )
    forums_watch_after_reply = forms.BooleanField(
        required=False, initial=True, label=_lazy(u"Watch forum threads I comment in")
    )
    kbforums_watch_new_thread = forms.BooleanField(
        required=False,
        initial=True,
        label=_lazy(u"Watch KB discussion threads I start"),
    )
    kbforums_watch_after_reply = forms.BooleanField(
        required=False,
        initial=True,
        label=_lazy(u"Watch KB discussion threads I comment in"),
    )
    questions_watch_after_reply = forms.BooleanField(
        required=False,
        initial=True,
        label=_lazy(u"Watch Question threads I comment in"),
    )
    email_private_messages = forms.BooleanField(
        required=False, initial=True, label=_lazy(u"Send emails for private messages")
    )

    def save_for_user(self, user):
        for field in self.fields.keys():
            value = str(self.cleaned_data[field])
            setting = user.settings.filter(name=field)
            update_count = setting.update(value=value)
            if update_count == 0:
                # This user didn't have this setting so create it.
                user.settings.create(name=field, value=value)


class ProfileForm(forms.ModelForm):
    """The form for editing the user's profile."""

    involved_from = forms.DateField(
        required=False,
        label=_lazy(u"Involved with Mozilla from"),
        widget=MonthYearWidget(
            years=range(1998, datetime.today().year + 1), required=False
        ),
    )

    class Meta(object):
        model = Profile
        fields = (
            "name",
            "bio",
            "public_email",
            "website",
            "twitter",
            "facebook",
            "mozillians",
            "irc_handle",
            "country",
            "city",
            "timezone",
            "locale",
            "involved_from",
        )

        widgets = {
            "facebook": FacebookURLWidget,
        }

    def __init__(self, *args, **kwargs):
        super(ProfileForm, self).__init__(*args, **kwargs)

        # # Add the public_email toggle if the user has not migrated to FxA yet
        if self.instance and self.instance.is_fxa_migrated:
            self.fields.pop("public_email")

        for field in self.fields.values():
            if isinstance(field, forms.CharField):
                field.empty_value = ""

    def clean_facebook(self):
        facebook = self.cleaned_data["facebook"]
        if facebook and not re.match(FacebookURLWidget.pattern, facebook):
            raise forms.ValidationError(_(u"Please enter a facebook.com URL."))
        return facebook


# This is used in groups/forms.py
class AvatarForm(forms.ModelForm):
    """The form for editing the user's avatar."""

    avatar = LimitedImageField(required=True, widget=ImageWidget)

    def __init__(self, *args, **kwargs):
        super(AvatarForm, self).__init__(*args, **kwargs)
        self.fields["avatar"].help_text = _(
            "Your avatar will be resized to {size}x{size}"
        ).format(size=settings.AVATAR_SIZE)

    class Meta(object):
        model = Profile
        fields = ("avatar",)

    def clean_avatar(self):
        if not ("avatar" in self.cleaned_data and self.cleaned_data["avatar"]):
            return self.cleaned_data["avatar"]
        try:
            check_file_size(self.cleaned_data["avatar"], settings.MAX_AVATAR_FILE_SIZE)
        except FileTooLargeError as e:
            raise forms.ValidationError(e.args[0])
        return self.cleaned_data["avatar"]


USERNAME_CACHE_KEY = "username-blacklist"


def username_allowed(username):
    if not username:
        return False
    """Returns True if the given username is not a blatent bad word."""
    blacklist = cache.get(USERNAME_CACHE_KEY)
    if blacklist is None:
        f = open(settings.USERNAME_BLACKLIST, "r")
        blacklist = [w.strip() for w in f.readlines()]
        cache.set(USERNAME_CACHE_KEY, blacklist, 60 * 60)  # 1 hour
    # Lowercase
    username = username.lower()
    # Add lowercased and non alphanumerics to start.
    usernames = set([username, re.sub(r"\W", "", username)])
    # Add words split on non alphanumerics.
    for u in re.findall(r"\w+", username):
        usernames.add(u)
    # Do any match the bad words?
    return not usernames.intersection(blacklist)


def _check_username(username):
    if username and not username_allowed(username):
        msg = _(
            "The user name you entered is inappropriate. Please pick "
            "another and consider that our helpers are other Firefox "
            "users just like you."
        )
        raise forms.ValidationError(msg)
