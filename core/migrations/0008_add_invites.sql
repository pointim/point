ALTER TABLE users.info
	ADD COLUMN inviter integer DEFAULT NULL;
ALTER TABLE users.profile
	ADD COLUMN allow_invite boolean DEFAULT true;
