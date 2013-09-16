CREATE TABLE `south_migrationhistory` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `app_name` varchar(255) NOT NULL,
  `migration` varchar(255) NOT NULL,
  `applied` datetime NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB CHARACTER SET utf8 COLLATE utf8_general_ci;


INSERT INTO `south_migrationhistory` (id, app_name, migration, applied) VALUES
(1,'announcements','0001_initial','2013-09-09 13:24:41'),
(2,'customercare','0001_initial','2013-09-09 13:24:50'),
(3,'dashboards','0001_initial','2013-09-09 13:24:54'),
(4,'flagit','0001_initial','2013-09-09 13:25:01'),
(5,'forums','0001_initial','2013-09-09 13:25:05'),
(6,'gallery','0001_initial','2013-09-09 13:25:08'),
(7,'groups','0001_initial','2013-09-09 13:25:11'),
(8,'inproduct','0001_initial','2013-09-09 13:25:15'),
(9,'karma','0001_initial','2013-09-09 13:25:22'),
(10,'kbforums','0001_initial','2013-09-09 13:25:30'),
(11,'kpi','0001_initial','2013-09-09 13:25:33'),
(12,'postcrash','0001_initial','2013-09-09 13:25:56'),
(13,'products','0001_initial','2013-09-09 13:26:01'),
(14,'questions','0001_initial','2013-09-09 13:26:05'),
(15,'search','0001_initial','2013-09-09 13:26:08'),
(16,'upload','0001_initial','2013-09-09 13:26:25'),
(17,'users','0001_initial','2013-09-09 13:32:57'),
(18,'djcelery','0001_initial','2013-09-09 13:47:45'),
(19,'djcelery','0002_v25_changes','2013-09-09 13:47:45'),
(20,'badger','0001_initial','2013-09-09 13:47:54'),
(21,'badger','0002_auto__add_deferredaward__add_field_badge_nominations_accepted','2013-09-09 13:47:54'),
(22,'badger','0003_auto__add_field_award_claim_code__chg_field_deferredaward_claim_code','2013-09-09 13:47:54'),
(23,'badger','0004_auto__add_nomination','2013-09-09 13:47:54'),
(24,'badger','0005_auto__add_field_award_description','2013-09-09 13:47:54'),
(25,'badger','0006_auto__add_field_nomination_rejecter__add_field_nomination_rejection_re','2013-09-09 13:47:54'),
(26,'badger','0007_auto__add_field_badge_nominations_autoapproved','2013-09-09 13:47:54'),
(27,'waffle','0001_initial','2013-09-09 13:48:03'),
(28,'waffle','0002_auto__add_sample','2013-09-09 13:48:03'),
(29,'waffle','0003_auto__add_field_flag_note__add_field_switch_note__add_field_sample_not','2013-09-09 13:48:03'),
(30,'waffle','0004_auto__add_field_flag_testing','2013-09-09 13:48:03'),
(31,'waffle','0005_auto__add_field_flag_created__add_field_flag_modified','2013-09-09 13:48:03'),
(32,'waffle','0006_auto__add_field_switch_created__add_field_switch_modified__add_field_s','2013-09-09 13:48:03'),
(33,'waffle','0007_auto__chg_field_flag_created__chg_field_flag_modified__chg_field_switc','2013-09-09 13:48:03'),
(34,'waffle','0008_auto__add_field_flag_languages','2013-09-09 13:48:03');