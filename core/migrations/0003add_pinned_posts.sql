ALTER TABLE posts.posts
	ADD COLUMN pinned boolean NOT NULL DEFAULT FALSE;

CREATE INDEX posts_pinned_idx ON posts.posts USING btree(pinned DESC);
