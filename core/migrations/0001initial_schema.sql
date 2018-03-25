--
-- PostgreSQL database dump
--

SET statement_timeout = 0;
SET lock_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SET check_function_bodies = false;
SET client_min_messages = warning;

--
-- Name: posts; Type: SCHEMA; Schema: -; Owner: point
--

CREATE SCHEMA posts;


ALTER SCHEMA posts OWNER TO point;

--
-- Name: subs; Type: SCHEMA; Schema: -; Owner: point
--

CREATE SCHEMA subs;


ALTER SCHEMA subs OWNER TO point;

--
-- Name: users; Type: SCHEMA; Schema: -; Owner: point
--

CREATE SCHEMA users;


ALTER SCHEMA users OWNER TO point;

--
-- Name: plpgsql; Type: EXTENSION; Schema: -; Owner: 
--

CREATE EXTENSION IF NOT EXISTS plpgsql WITH SCHEMA pg_catalog;


--
-- Name: EXTENSION plpgsql; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION plpgsql IS 'PL/pgSQL procedural language';


SET search_path = posts, pg_catalog;

--
-- Name: post_type; Type: TYPE; Schema: posts; Owner: point
--

CREATE TYPE post_type AS ENUM (
    'post',
    'feed'
);


ALTER TYPE posts.post_type OWNER TO point;

SET search_path = users, pg_catalog;

--
-- Name: account_type; Type: TYPE; Schema: users; Owner: point
--

CREATE TYPE account_type AS ENUM (
    'xmpp',
    'icq',
    'email'
);


ALTER TYPE users.account_type OWNER TO point;

--
-- Name: user_type; Type: TYPE; Schema: users; Owner: point
--

CREATE TYPE user_type AS ENUM (
    'user',
    'group',
    'feed'
);


ALTER TYPE users.user_type OWNER TO point;

SET search_path = posts, pg_catalog;

--
-- Name: delete_recommendation_recent(); Type: FUNCTION; Schema: posts; Owner: point
--

CREATE FUNCTION delete_recommendation_recent() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    DELETE FROM "posts"."recent"
    WHERE user_id=OLD.user_id AND post_id=OLD.post_id
        AND comment_id=OLD.comment_id;

    DELETE FROM "posts"."recent_blog"
    WHERE user_id=OLD.user_id AND post_id=OLD.post_id
        AND comment_id=OLD.comment_id;
    RETURN OLD;
END;
$$;


ALTER FUNCTION posts.delete_recommendation_recent() OWNER TO point;

--
-- Name: insert_post_by_type(); Type: FUNCTION; Schema: posts; Owner: point
--

CREATE FUNCTION insert_post_by_type() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
  IF new."type" = 'feed' THEN
    INSERT INTO "posts"."feeds" VALUES (new.*);
  ELSE
    INSERT INTO "posts"."posts" VALUES (new.*);
  END IF;
  RETURN null;
END;
$$;


ALTER FUNCTION posts.insert_post_by_type() OWNER TO point;

--
-- Name: insert_post_recent(); Type: FUNCTION; Schema: posts; Owner: point
--

CREATE FUNCTION insert_post_recent() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
    u record;
BEGIN
    IF NEW.private THEN
        RETURN NEW;
    END IF;
    FOR u IN
    SELECT user_id FROM subs.users WHERE to_user_id = NEW.author
    UNION
    SELECT user_id FROM subs.tags_global WHERE tag = ANY(NEW.tags)
    UNION
    SELECT user_id FROM subs.tags_user WHERE to_user_id = NEW.author
        AND LOWER(tag) = ANY(public.array_lowercase(NEW.tags))
    EXCEPT
    SELECT user_id FROM posts.tags_blacklist_global WHERE
        LOWER(tag) = ANY(public.array_lowercase(NEW.tags))
    EXCEPT
    SELECT user_id FROM posts.tags_blacklist_user WHERE to_user_id = NEW.author
        AND LOWER(tag) = ANY(public.array_lowercase(NEW.tags))
    EXCEPT
    SELECT user_id FROM users.blacklist WHERE to_user_id = NEW.author
    LOOP
        INSERT INTO posts.recent (rcpt_id, user_id, post_id, created)
        VALUES (u.user_id, NEW.author, NEW.id, NEW.created);
    END LOOP;

    INSERT INTO posts.recent_blog (user_id, post_id, created)
    VALUES (NEW.author, NEW.id, NEW.created);
    RETURN NEW;
END;
$$;


ALTER FUNCTION posts.insert_post_recent() OWNER TO point;

--
-- Name: insert_recommendation_recent(); Type: FUNCTION; Schema: posts; Owner: point
--

CREATE FUNCTION insert_recommendation_recent() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
    post_author bigint;
    post_tags text[];
    comment_author bigint;
    u record;
    priv boolean;
BEGIN
    SELECT author, tags INTO post_author, post_tags FROM posts.posts WHERE id = NEW.post_id;
    IF NEW.comment_id IS NOT NULL AND NEW.comment_id > 0 THEN
        SELECT author INTO comment_author FROM posts.comments
            WHERE post_id = NEW.post_id AND comment_id = NEW.comment_id;
    ELSE
        comment_author := 0;
    END IF;

    SELECT private INTO priv FROM users.profile WHERE id=post_author;

    IF priv THEN
        FOR u IN
        ((SELECT user_id FROM subs.users WHERE to_user_id = NEW.user_id
                                              AND user_id != post_author
                                              AND user_id != comment_author
        EXCEPT
        SELECT user_id FROM users.blacklist
            WHERE to_user_id IN (post_author, comment_author))
        EXCEPT
        SELECT user_id FROM posts.recommendations_recv
            WHERE post_id = NEW.post_id AND comment_id = NEW.comment_id)
        EXCEPT
        SELECT user_id FROM posts.tags_blacklist_user
            WHERE to_user_id=post_author AND tag=ANY(post_tags)
        EXCEPT
        SELECT user_id FROM posts.tags_blacklist_global
            WHERE tag=ANY(post_tags)
        INTERSECT
        SELECT to_user_id FROM users.whitelist WHERE user_id=post_author
        LOOP
            INSERT INTO posts.recent (rcpt_id, user_id, is_rec, post_id, comment_id, created, rcid)
            VALUES (u.user_id, NEW.user_id, true, NEW.post_id, NEW.comment_id, NEW.created, NEW.rcid);
        END LOOP;
    ELSE
        FOR u IN
        (SELECT user_id FROM subs.users WHERE to_user_id = NEW.user_id
                                              AND user_id != post_author
                                              AND user_id != comment_author
        EXCEPT
        SELECT user_id FROM posts.tags_blacklist_user
            WHERE to_user_id=post_author AND tag=ANY(post_tags)
        EXCEPT
        SELECT user_id FROM posts.tags_blacklist_global
            WHERE tag=ANY(post_tags)
        EXCEPT
        SELECT user_id FROM users.blacklist
            WHERE to_user_id IN (post_author, comment_author))
        EXCEPT
        SELECT user_id FROM posts.recommendations_recv
            WHERE post_id = NEW.post_id AND comment_id = NEW.comment_id
        LOOP
            INSERT INTO posts.recent (rcpt_id, user_id, is_rec, post_id, comment_id, created, rcid)
            VALUES (u.user_id, NEW.user_id, true, NEW.post_id, NEW.comment_id, NEW.created, NEW.rcid);
        END LOOP;
    END IF;

    INSERT INTO posts.recent_blog
    (user_id, is_rec, post_id, comment_id, created, rcid)
    VALUES (NEW.user_id, true, NEW.post_id, NEW.comment_id, NEW.created, NEW.rcid);
    RETURN NEW;
END;
$$;


ALTER FUNCTION posts.insert_recommendation_recent() OWNER TO point;

--
-- Name: insert_tags_blacklist(); Type: FUNCTION; Schema: posts; Owner: point
--

CREATE FUNCTION insert_tags_blacklist() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    IF new.to_user_id IS NULL THEN
        INSERT INTO "posts"."tags_blacklist_global"
            VALUES (new.user_id, null, new.tag);
    ELSE
        INSERT INTO "posts"."tags_blacklist_user"
            VALUES (new.user_id, new.to_user_id, new.tag);
    END IF;
    RETURN null;
END;
$$;


ALTER FUNCTION posts.insert_tags_blacklist() OWNER TO point;

SET search_path = public, pg_catalog;

--
-- Name: array_lowercase(character varying[]); Type: FUNCTION; Schema: public; Owner: point
--

CREATE FUNCTION array_lowercase(character varying[]) RETURNS character varying[]
    LANGUAGE sql IMMUTABLE
    AS $_$
  SELECT array_agg(q.tag) FROM (
    SELECT btrim(lower(unnest($1)))::varchar AS tag
  ) AS q;
$_$;


ALTER FUNCTION public.array_lowercase(character varying[]) OWNER TO point;

--
-- Name: comment_delete(); Type: FUNCTION; Schema: public; Owner: point
--

CREATE FUNCTION comment_delete() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    DELETE FROM posts.recommendations
    WHERE post_id=OLD.post_id AND comment_id=OLD.comment_id;
    RETURN OLD;
END;
$$;


ALTER FUNCTION public.comment_delete() OWNER TO point;

SET search_path = subs, pg_catalog;

--
-- Name: insert_tags(); Type: FUNCTION; Schema: subs; Owner: point
--

CREATE FUNCTION insert_tags() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    IF new.to_user_id IS NULL THEN
        INSERT INTO "subs"."tags_global"
            VALUES (new.user_id, null, new.tag);
    ELSE
        INSERT INTO "subs"."tags_user"
            VALUES (new.user_id, new.to_user_id, new.tag);
    END IF;
    RETURN null;
END;
$$;


ALTER FUNCTION subs.insert_tags() OWNER TO point;

SET search_path = posts, pg_catalog;

SET default_tablespace = '';

SET default_with_oids = false;

--
-- Name: bookmarks; Type: TABLE; Schema: posts; Owner: point; Tablespace: 
--

CREATE TABLE bookmarks (
    user_id integer NOT NULL,
    post_id bigint NOT NULL,
    comment_id integer DEFAULT 0 NOT NULL,
    created timestamp with time zone DEFAULT now(),
    btext text
);


ALTER TABLE posts.bookmarks OWNER TO point;

--
-- Name: comments; Type: TABLE; Schema: posts; Owner: point; Tablespace: 
--

CREATE TABLE comments (
    id bigint NOT NULL,
    post_id bigint NOT NULL,
    comment_id integer NOT NULL,
    author bigint NOT NULL,
    to_user_id integer,
    to_comment_id integer,
    created timestamp with time zone DEFAULT now(),
    text text NOT NULL,
    anon_login text,
    files text[]
);


ALTER TABLE posts.comments OWNER TO point;

--
-- Name: comments_id_seq; Type: SEQUENCE; Schema: posts; Owner: point
--

CREATE SEQUENCE comments_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE posts.comments_id_seq OWNER TO point;

--
-- Name: comments_id_seq; Type: SEQUENCE OWNED BY; Schema: posts; Owner: point
--

ALTER SEQUENCE comments_id_seq OWNED BY comments.id;


--
-- Name: posts; Type: TABLE; Schema: posts; Owner: point; Tablespace: 
--

CREATE TABLE posts (
    id bigint NOT NULL,
    author bigint NOT NULL,
    type post_type DEFAULT 'post'::post_type NOT NULL,
    private boolean DEFAULT false,
    created timestamp with time zone DEFAULT now(),
    resource text,
    tags text[],
    text text NOT NULL,
    rpost bigint,
    rcomment integer,
    rcreated timestamp without time zone,
    rtext text,
    edited boolean DEFAULT false,
    title text,
    link text,
    archive boolean DEFAULT false,
    files text[]
);


ALTER TABLE posts.posts OWNER TO point;

--
-- Name: posts_id_seq; Type: SEQUENCE; Schema: posts; Owner: point
--

CREATE SEQUENCE posts_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE posts.posts_id_seq OWNER TO point;

--
-- Name: posts_id_seq; Type: SEQUENCE OWNED BY; Schema: posts; Owner: point
--

ALTER SEQUENCE posts_id_seq OWNED BY posts.id;


--
-- Name: recent; Type: TABLE; Schema: posts; Owner: point; Tablespace: 
--

CREATE TABLE recent (
    id bigint NOT NULL,
    rcpt_id bigint NOT NULL,
    user_id bigint NOT NULL,
    is_rec boolean DEFAULT false,
    post_id bigint,
    comment_id integer DEFAULT 0 NOT NULL,
    created timestamp with time zone DEFAULT now(),
    rcid bigint
);


ALTER TABLE posts.recent OWNER TO point;

--
-- Name: recent_blog; Type: TABLE; Schema: posts; Owner: point; Tablespace: 
--

CREATE TABLE recent_blog (
    id bigint NOT NULL,
    user_id bigint NOT NULL,
    is_rec boolean DEFAULT false,
    post_id bigint,
    comment_id integer DEFAULT 0 NOT NULL,
    created timestamp with time zone DEFAULT now(),
    rcid bigint
);


ALTER TABLE posts.recent_blog OWNER TO point;

--
-- Name: recent_blog_id_seq; Type: SEQUENCE; Schema: posts; Owner: point
--

CREATE SEQUENCE recent_blog_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE posts.recent_blog_id_seq OWNER TO point;

--
-- Name: recent_blog_id_seq; Type: SEQUENCE OWNED BY; Schema: posts; Owner: point
--

ALTER SEQUENCE recent_blog_id_seq OWNED BY recent_blog.id;


--
-- Name: recent_id_seq; Type: SEQUENCE; Schema: posts; Owner: point
--

CREATE SEQUENCE recent_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE posts.recent_id_seq OWNER TO point;

--
-- Name: recent_id_seq; Type: SEQUENCE OWNED BY; Schema: posts; Owner: point
--

ALTER SEQUENCE recent_id_seq OWNED BY recent.id;


--
-- Name: recipients; Type: TABLE; Schema: posts; Owner: point; Tablespace: 
--

CREATE TABLE recipients (
    post_id bigint NOT NULL,
    user_id integer NOT NULL
);


ALTER TABLE posts.recipients OWNER TO point;

--
-- Name: recommendations; Type: TABLE; Schema: posts; Owner: point; Tablespace: 
--

CREATE TABLE recommendations (
    post_id bigint NOT NULL,
    comment_id bigint NOT NULL,
    user_id integer NOT NULL,
    text text,
    rcid bigint,
    created timestamp with time zone DEFAULT now()
);


ALTER TABLE posts.recommendations OWNER TO point;

--
-- Name: recommendations_recv; Type: TABLE; Schema: posts; Owner: point; Tablespace: 
--

CREATE TABLE recommendations_recv (
    post_id bigint NOT NULL,
    comment_id bigint NOT NULL,
    user_id integer NOT NULL,
    text text
);


ALTER TABLE posts.recommendations_recv OWNER TO point;

--
-- Name: tags; Type: TABLE; Schema: posts; Owner: point; Tablespace: 
--

CREATE TABLE tags (
    post_id bigint NOT NULL,
    user_id integer NOT NULL,
    tag text NOT NULL
);


ALTER TABLE posts.tags OWNER TO point;

--
-- Name: tags_blacklist; Type: TABLE; Schema: posts; Owner: point; Tablespace: 
--

CREATE TABLE tags_blacklist (
    user_id bigint NOT NULL,
    to_user_id bigint,
    tag text NOT NULL
);


ALTER TABLE posts.tags_blacklist OWNER TO point;

--
-- Name: tags_blacklist_global; Type: TABLE; Schema: posts; Owner: point; Tablespace: 
--

CREATE TABLE tags_blacklist_global (
    CONSTRAINT tags_blacklist_global_to_user_id_check CHECK ((to_user_id IS NULL))
)
INHERITS (tags_blacklist);


ALTER TABLE posts.tags_blacklist_global OWNER TO point;

--
-- Name: tags_blacklist_user; Type: TABLE; Schema: posts; Owner: point; Tablespace: 
--

CREATE TABLE tags_blacklist_user (
    CONSTRAINT tags_blacklist_user_to_user_id_check CHECK ((to_user_id IS NOT NULL))
)
INHERITS (tags_blacklist);
ALTER TABLE ONLY tags_blacklist_user ALTER COLUMN to_user_id SET NOT NULL;


ALTER TABLE posts.tags_blacklist_user OWNER TO point;

--
-- Name: unread_comments; Type: TABLE; Schema: posts; Owner: point; Tablespace: 
--

CREATE TABLE unread_comments (
    user_id integer NOT NULL,
    post_id bigint NOT NULL,
    comment_id integer NOT NULL,
    type text DEFAULT 'post'::text,
    created timestamp with time zone DEFAULT now()
);


ALTER TABLE posts.unread_comments OWNER TO point;

--
-- Name: unread_posts; Type: TABLE; Schema: posts; Owner: point; Tablespace: 
--

CREATE TABLE unread_posts (
    user_id integer NOT NULL,
    post_id bigint NOT NULL,
    type text DEFAULT 'post'::text
);


ALTER TABLE posts.unread_posts OWNER TO point;

--
-- Name: updates; Type: TABLE; Schema: posts; Owner: point; Tablespace: 
--

CREATE TABLE updates (
    post_id bigint NOT NULL,
    created timestamp with time zone DEFAULT now() NOT NULL,
    text text NOT NULL
);


ALTER TABLE posts.updates OWNER TO point;

SET search_path = public, pg_catalog;

--
-- Name: test; Type: TABLE; Schema: public; Owner: point; Tablespace: 
--

CREATE TABLE test (
    ts timestamp without time zone
);


ALTER TABLE public.test OWNER TO point;

SET search_path = subs, pg_catalog;

--
-- Name: posts; Type: TABLE; Schema: subs; Owner: point; Tablespace: 
--

CREATE TABLE posts (
    user_id bigint NOT NULL,
    post_id bigint NOT NULL
);


ALTER TABLE subs.posts OWNER TO point;

--
-- Name: recommendations; Type: TABLE; Schema: subs; Owner: point; Tablespace: 
--

CREATE TABLE recommendations (
    user_id integer NOT NULL,
    to_user_id integer NOT NULL
);


ALTER TABLE subs.recommendations OWNER TO point;

--
-- Name: requests; Type: TABLE; Schema: subs; Owner: point; Tablespace: 
--

CREATE TABLE requests (
    user_id integer NOT NULL,
    to_user_id integer NOT NULL
);


ALTER TABLE subs.requests OWNER TO point;

--
-- Name: tags; Type: TABLE; Schema: subs; Owner: point; Tablespace: 
--

CREATE TABLE tags (
    user_id bigint NOT NULL,
    to_user_id bigint,
    tag text NOT NULL
);


ALTER TABLE subs.tags OWNER TO point;

--
-- Name: tags_global; Type: TABLE; Schema: subs; Owner: point; Tablespace: 
--

CREATE TABLE tags_global (
    CONSTRAINT tags_global_to_user_id_check CHECK ((to_user_id IS NULL))
)
INHERITS (tags);


ALTER TABLE subs.tags_global OWNER TO point;

--
-- Name: tags_user; Type: TABLE; Schema: subs; Owner: point; Tablespace: 
--

CREATE TABLE tags_user (
    CONSTRAINT tags_user_to_user_id_check CHECK ((to_user_id IS NOT NULL))
)
INHERITS (tags);
ALTER TABLE ONLY tags_user ALTER COLUMN to_user_id SET NOT NULL;


ALTER TABLE subs.tags_user OWNER TO point;

--
-- Name: users; Type: TABLE; Schema: subs; Owner: point; Tablespace: 
--

CREATE TABLE users (
    user_id integer NOT NULL,
    to_user_id integer NOT NULL
);


ALTER TABLE subs.users OWNER TO point;

SET search_path = users, pg_catalog;

--
-- Name: accounts; Type: TABLE; Schema: users; Owner: point; Tablespace: 
--

CREATE TABLE accounts (
    id integer NOT NULL,
    user_id integer,
    type account_type NOT NULL,
    address text
);


ALTER TABLE users.accounts OWNER TO point;

--
-- Name: accounts_id_seq; Type: SEQUENCE; Schema: users; Owner: point
--

CREATE SEQUENCE accounts_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE users.accounts_id_seq OWNER TO point;

--
-- Name: accounts_id_seq; Type: SEQUENCE OWNED BY; Schema: users; Owner: point
--

ALTER SEQUENCE accounts_id_seq OWNED BY accounts.id;


--
-- Name: accounts_unconfirmed; Type: TABLE; Schema: users; Owner: point; Tablespace: 
--

CREATE TABLE accounts_unconfirmed (
    id integer NOT NULL,
    user_id integer,
    type account_type NOT NULL,
    address text NOT NULL,
    code character(40) NOT NULL
);


ALTER TABLE users.accounts_unconfirmed OWNER TO point;

--
-- Name: accounts_unconfirmed_id_seq; Type: SEQUENCE; Schema: users; Owner: point
--

CREATE SEQUENCE accounts_unconfirmed_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE users.accounts_unconfirmed_id_seq OWNER TO point;

--
-- Name: accounts_unconfirmed_id_seq; Type: SEQUENCE OWNED BY; Schema: users; Owner: point
--

ALTER SEQUENCE accounts_unconfirmed_id_seq OWNED BY accounts_unconfirmed.id;


--
-- Name: aliases; Type: TABLE; Schema: users; Owner: point; Tablespace: 
--

CREATE TABLE aliases (
    alias character varying(255) NOT NULL,
    command text NOT NULL
);


ALTER TABLE users.aliases OWNER TO point;

--
-- Name: blacklist; Type: TABLE; Schema: users; Owner: point; Tablespace: 
--

CREATE TABLE blacklist (
    user_id integer NOT NULL,
    to_user_id integer NOT NULL
);


ALTER TABLE users.blacklist OWNER TO point;

--
-- Name: domains; Type: TABLE; Schema: users; Owner: point; Tablespace: 
--

CREATE TABLE domains (
    id integer NOT NULL,
    domain text NOT NULL
);


ALTER TABLE users.domains OWNER TO point;

--
-- Name: feeds; Type: TABLE; Schema: users; Owner: point; Tablespace: 
--

CREATE TABLE feeds (
    id bigint NOT NULL,
    url text NOT NULL
);


ALTER TABLE users.feeds OWNER TO point;

--
-- Name: info; Type: TABLE; Schema: users; Owner: point; Tablespace: 
--

CREATE TABLE info (
    id bigint NOT NULL,
    name text,
    created timestamp with time zone DEFAULT now(),
    gender boolean,
    avatar text,
    email text,
    xmpp text,
    icq text,
    skype text,
    about text DEFAULT ''::text,
    birthdate date,
    location text,
    homepage text
);


ALTER TABLE users.info OWNER TO point;

--
-- Name: logins; Type: TABLE; Schema: users; Owner: point; Tablespace: 
--

CREATE TABLE logins (
    id integer NOT NULL,
    login character varying(32) NOT NULL,
    password character(40),
    type user_type DEFAULT 'user'::user_type
);


ALTER TABLE users.logins OWNER TO point;

--
-- Name: logins_id_seq; Type: SEQUENCE; Schema: users; Owner: point
--

CREATE SEQUENCE logins_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE users.logins_id_seq OWNER TO point;

--
-- Name: logins_id_seq; Type: SEQUENCE OWNED BY; Schema: users; Owner: point
--

ALTER SEQUENCE logins_id_seq OWNED BY logins.id;


--
-- Name: profile; Type: TABLE; Schema: users; Owner: point; Tablespace: 
--

CREATE TABLE profile (
    id bigint NOT NULL,
    private boolean DEFAULT false,
    lang character(2) DEFAULT 'en'::bpchar,
    tz character varying DEFAULT 'Europe/Moscow'::character varying NOT NULL,
    deny_anonymous boolean DEFAULT false
);


ALTER TABLE users.profile OWNER TO point;

--
-- Name: profile_im; Type: TABLE; Schema: users; Owner: point; Tablespace: 
--

CREATE TABLE profile_im (
    id bigint NOT NULL,
    off boolean DEFAULT false,
    xhtml boolean DEFAULT false,
    highlight boolean DEFAULT false,
    user_resource boolean DEFAULT false,
    post_resource boolean DEFAULT false,
    cut integer,
    auto_switch boolean DEFAULT true
);


ALTER TABLE users.profile_im OWNER TO point;

--
-- Name: profile_www; Type: TABLE; Schema: users; Owner: point; Tablespace: 
--

CREATE TABLE profile_www (
    id bigint NOT NULL,
    blog_css text,
    global_css text,
    blogcss text,
    usercss text,
    ignorecss boolean DEFAULT false,
    tree boolean DEFAULT false
);


ALTER TABLE users.profile_www OWNER TO point;

--
-- Name: ulogin_accounts; Type: TABLE; Schema: users; Owner: point; Tablespace: 
--

CREATE TABLE ulogin_accounts (
    id bigint NOT NULL,
    network text NOT NULL,
    uid text NOT NULL,
    nickname text,
    name text,
    profile text
);


ALTER TABLE users.ulogin_accounts OWNER TO point;

--
-- Name: user_aliases; Type: TABLE; Schema: users; Owner: point; Tablespace: 
--

CREATE TABLE user_aliases (
    user_id integer NOT NULL,
    alias character varying(255) NOT NULL,
    command text NOT NULL
);


ALTER TABLE users.user_aliases OWNER TO point;

--
-- Name: whitelist; Type: TABLE; Schema: users; Owner: point; Tablespace: 
--

CREATE TABLE whitelist (
    user_id integer NOT NULL,
    to_user_id integer NOT NULL
);


ALTER TABLE users.whitelist OWNER TO point;

SET search_path = posts, pg_catalog;

--
-- Name: id; Type: DEFAULT; Schema: posts; Owner: point
--

ALTER TABLE ONLY comments ALTER COLUMN id SET DEFAULT nextval('comments_id_seq'::regclass);


--
-- Name: id; Type: DEFAULT; Schema: posts; Owner: point
--

ALTER TABLE ONLY posts ALTER COLUMN id SET DEFAULT nextval('posts_id_seq'::regclass);


--
-- Name: id; Type: DEFAULT; Schema: posts; Owner: point
--

ALTER TABLE ONLY recent ALTER COLUMN id SET DEFAULT nextval('recent_id_seq'::regclass);


--
-- Name: id; Type: DEFAULT; Schema: posts; Owner: point
--

ALTER TABLE ONLY recent_blog ALTER COLUMN id SET DEFAULT nextval('recent_blog_id_seq'::regclass);


SET search_path = users, pg_catalog;

--
-- Name: id; Type: DEFAULT; Schema: users; Owner: point
--

ALTER TABLE ONLY accounts ALTER COLUMN id SET DEFAULT nextval('accounts_id_seq'::regclass);


--
-- Name: id; Type: DEFAULT; Schema: users; Owner: point
--

ALTER TABLE ONLY accounts_unconfirmed ALTER COLUMN id SET DEFAULT nextval('accounts_unconfirmed_id_seq'::regclass);


--
-- Name: id; Type: DEFAULT; Schema: users; Owner: point
--

ALTER TABLE ONLY logins ALTER COLUMN id SET DEFAULT nextval('logins_id_seq'::regclass);


SET search_path = posts, pg_catalog;

--
-- Name: bookmarks_pkey; Type: CONSTRAINT; Schema: posts; Owner: point; Tablespace: 
--

ALTER TABLE ONLY bookmarks
    ADD CONSTRAINT bookmarks_pkey PRIMARY KEY (user_id, post_id, comment_id);


--
-- Name: comments_pkey; Type: CONSTRAINT; Schema: posts; Owner: point; Tablespace: 
--

ALTER TABLE ONLY comments
    ADD CONSTRAINT comments_pkey PRIMARY KEY (post_id, comment_id);


--
-- Name: posts_pkey; Type: CONSTRAINT; Schema: posts; Owner: point; Tablespace: 
--

ALTER TABLE ONLY posts
    ADD CONSTRAINT posts_pkey PRIMARY KEY (id);


--
-- Name: recent_blog_pkey; Type: CONSTRAINT; Schema: posts; Owner: point; Tablespace: 
--

ALTER TABLE ONLY recent_blog
    ADD CONSTRAINT recent_blog_pkey PRIMARY KEY (id);


--
-- Name: recent_pkey; Type: CONSTRAINT; Schema: posts; Owner: point; Tablespace: 
--

ALTER TABLE ONLY recent
    ADD CONSTRAINT recent_pkey PRIMARY KEY (id);


--
-- Name: recipients_pkey; Type: CONSTRAINT; Schema: posts; Owner: point; Tablespace: 
--

ALTER TABLE ONLY recipients
    ADD CONSTRAINT recipients_pkey PRIMARY KEY (post_id, user_id);


--
-- Name: recommendations_pkey; Type: CONSTRAINT; Schema: posts; Owner: point; Tablespace: 
--

ALTER TABLE ONLY recommendations
    ADD CONSTRAINT recommendations_pkey PRIMARY KEY (user_id, post_id, comment_id);


--
-- Name: recommendations_recv_pkey; Type: CONSTRAINT; Schema: posts; Owner: point; Tablespace: 
--

ALTER TABLE ONLY recommendations_recv
    ADD CONSTRAINT recommendations_recv_pkey PRIMARY KEY (user_id, post_id, comment_id);


--
-- Name: tags_blacklist_global_pkey; Type: CONSTRAINT; Schema: posts; Owner: point; Tablespace: 
--

ALTER TABLE ONLY tags_blacklist_global
    ADD CONSTRAINT tags_blacklist_global_pkey PRIMARY KEY (user_id, tag);


--
-- Name: tags_blacklist_user_pkey; Type: CONSTRAINT; Schema: posts; Owner: point; Tablespace: 
--

ALTER TABLE ONLY tags_blacklist_user
    ADD CONSTRAINT tags_blacklist_user_pkey PRIMARY KEY (user_id, to_user_id, tag);


--
-- Name: tags_pkey; Type: CONSTRAINT; Schema: posts; Owner: point; Tablespace: 
--

ALTER TABLE ONLY tags
    ADD CONSTRAINT tags_pkey PRIMARY KEY (post_id, user_id, tag);


--
-- Name: unread_commets_pkey; Type: CONSTRAINT; Schema: posts; Owner: point; Tablespace: 
--

ALTER TABLE ONLY unread_comments
    ADD CONSTRAINT unread_commets_pkey PRIMARY KEY (user_id, post_id, comment_id);


--
-- Name: unread_posts_pkey; Type: CONSTRAINT; Schema: posts; Owner: point; Tablespace: 
--

ALTER TABLE ONLY unread_posts
    ADD CONSTRAINT unread_posts_pkey PRIMARY KEY (user_id, post_id);


--
-- Name: updates_pkey; Type: CONSTRAINT; Schema: posts; Owner: point; Tablespace: 
--

ALTER TABLE ONLY updates
    ADD CONSTRAINT updates_pkey PRIMARY KEY (post_id, created);


SET search_path = subs, pg_catalog;

--
-- Name: posts_pkey; Type: CONSTRAINT; Schema: subs; Owner: point; Tablespace: 
--

ALTER TABLE ONLY posts
    ADD CONSTRAINT posts_pkey PRIMARY KEY (user_id, post_id);


--
-- Name: recommendations_pkey; Type: CONSTRAINT; Schema: subs; Owner: point; Tablespace: 
--

ALTER TABLE ONLY recommendations
    ADD CONSTRAINT recommendations_pkey PRIMARY KEY (user_id, to_user_id);


--
-- Name: requests_pkey; Type: CONSTRAINT; Schema: subs; Owner: point; Tablespace: 
--

ALTER TABLE ONLY requests
    ADD CONSTRAINT requests_pkey PRIMARY KEY (user_id, to_user_id);


--
-- Name: tags_global_pkey; Type: CONSTRAINT; Schema: subs; Owner: point; Tablespace: 
--

ALTER TABLE ONLY tags_global
    ADD CONSTRAINT tags_global_pkey PRIMARY KEY (user_id, tag);


--
-- Name: tags_user_pkey; Type: CONSTRAINT; Schema: subs; Owner: point; Tablespace: 
--

ALTER TABLE ONLY tags_user
    ADD CONSTRAINT tags_user_pkey PRIMARY KEY (user_id, to_user_id, tag);


--
-- Name: users_pkey; Type: CONSTRAINT; Schema: subs; Owner: point; Tablespace: 
--

ALTER TABLE ONLY users
    ADD CONSTRAINT users_pkey PRIMARY KEY (user_id, to_user_id);


SET search_path = users, pg_catalog;

--
-- Name: accounts_pkey; Type: CONSTRAINT; Schema: users; Owner: point; Tablespace: 
--

ALTER TABLE ONLY accounts
    ADD CONSTRAINT accounts_pkey PRIMARY KEY (id);


--
-- Name: accounts_unconfirmed_pkey; Type: CONSTRAINT; Schema: users; Owner: point; Tablespace: 
--

ALTER TABLE ONLY accounts_unconfirmed
    ADD CONSTRAINT accounts_unconfirmed_pkey PRIMARY KEY (id);


--
-- Name: aliases_pkey; Type: CONSTRAINT; Schema: users; Owner: point; Tablespace: 
--

ALTER TABLE ONLY aliases
    ADD CONSTRAINT aliases_pkey PRIMARY KEY (alias);


--
-- Name: blacklist_pkey; Type: CONSTRAINT; Schema: users; Owner: point; Tablespace: 
--

ALTER TABLE ONLY blacklist
    ADD CONSTRAINT blacklist_pkey PRIMARY KEY (user_id, to_user_id);


--
-- Name: feeds_pkey; Type: CONSTRAINT; Schema: users; Owner: point; Tablespace: 
--

ALTER TABLE ONLY feeds
    ADD CONSTRAINT feeds_pkey PRIMARY KEY (id);


--
-- Name: feeds_url_key; Type: CONSTRAINT; Schema: users; Owner: point; Tablespace: 
--

ALTER TABLE ONLY feeds
    ADD CONSTRAINT feeds_url_key UNIQUE (url);


--
-- Name: info_pkey; Type: CONSTRAINT; Schema: users; Owner: point; Tablespace: 
--

ALTER TABLE ONLY info
    ADD CONSTRAINT info_pkey PRIMARY KEY (id);


--
-- Name: logins_login_key; Type: CONSTRAINT; Schema: users; Owner: point; Tablespace: 
--

ALTER TABLE ONLY logins
    ADD CONSTRAINT logins_login_key UNIQUE (login);


--
-- Name: logins_pkey; Type: CONSTRAINT; Schema: users; Owner: point; Tablespace: 
--

ALTER TABLE ONLY logins
    ADD CONSTRAINT logins_pkey PRIMARY KEY (id);


--
-- Name: profile_im_pkey; Type: CONSTRAINT; Schema: users; Owner: point; Tablespace: 
--

ALTER TABLE ONLY profile_im
    ADD CONSTRAINT profile_im_pkey PRIMARY KEY (id);


--
-- Name: profile_pkey; Type: CONSTRAINT; Schema: users; Owner: point; Tablespace: 
--

ALTER TABLE ONLY profile
    ADD CONSTRAINT profile_pkey PRIMARY KEY (id);


--
-- Name: profile_www_pkey; Type: CONSTRAINT; Schema: users; Owner: point; Tablespace: 
--

ALTER TABLE ONLY profile_www
    ADD CONSTRAINT profile_www_pkey PRIMARY KEY (id);


--
-- Name: ulogin_accounts_pkey; Type: CONSTRAINT; Schema: users; Owner: point; Tablespace: 
--

ALTER TABLE ONLY ulogin_accounts
    ADD CONSTRAINT ulogin_accounts_pkey PRIMARY KEY (network, uid);


--
-- Name: user_aliases_pkey; Type: CONSTRAINT; Schema: users; Owner: point; Tablespace: 
--

ALTER TABLE ONLY user_aliases
    ADD CONSTRAINT user_aliases_pkey PRIMARY KEY (user_id, alias);


--
-- Name: whitelist_pkey; Type: CONSTRAINT; Schema: users; Owner: point; Tablespace: 
--

ALTER TABLE ONLY whitelist
    ADD CONSTRAINT whitelist_pkey PRIMARY KEY (user_id, to_user_id);


SET search_path = posts, pg_catalog;

--
-- Name: bookmarks_created_idx; Type: INDEX; Schema: posts; Owner: point; Tablespace: 
--

CREATE INDEX bookmarks_created_idx ON bookmarks USING btree (created DESC);


--
-- Name: bookmarks_post_id_comment_id_idx; Type: INDEX; Schema: posts; Owner: point; Tablespace: 
--

CREATE INDEX bookmarks_post_id_comment_id_idx ON bookmarks USING btree (post_id, comment_id);


--
-- Name: bookmarks_user_id_idx; Type: INDEX; Schema: posts; Owner: point; Tablespace: 
--

CREATE INDEX bookmarks_user_id_idx ON bookmarks USING btree (user_id);


--
-- Name: comments_author_idx; Type: INDEX; Schema: posts; Owner: point; Tablespace: 
--

CREATE INDEX comments_author_idx ON comments USING btree (author) WITH (fillfactor=40);


--
-- Name: comments_created_idx; Type: INDEX; Schema: posts; Owner: point; Tablespace: 
--

CREATE INDEX comments_created_idx ON comments USING btree (created) WITH (fillfactor=40);


--
-- Name: comments_id_idx; Type: INDEX; Schema: posts; Owner: point; Tablespace: 
--

CREATE UNIQUE INDEX comments_id_idx ON comments USING btree (id) WITH (fillfactor=40);


--
-- Name: comments_post_id_comment_id_idx; Type: INDEX; Schema: posts; Owner: point; Tablespace: 
--

CREATE INDEX comments_post_id_comment_id_idx ON comments USING btree (post_id, comment_id) WITH (fillfactor=40);


--
-- Name: comments_post_id_idx; Type: INDEX; Schema: posts; Owner: point; Tablespace: 
--

CREATE INDEX comments_post_id_idx ON comments USING btree (post_id) WITH (fillfactor=40);


--
-- Name: comments_to_comment_id_idx; Type: INDEX; Schema: posts; Owner: point; Tablespace: 
--

CREATE INDEX comments_to_comment_id_idx ON comments USING btree (to_comment_id) WITH (fillfactor=40);


--
-- Name: comments_to_user_id_idx; Type: INDEX; Schema: posts; Owner: point; Tablespace: 
--

CREATE INDEX comments_to_user_id_idx ON comments USING btree (to_user_id) WITH (fillfactor=40);


--
-- Name: posts_author_idx; Type: INDEX; Schema: posts; Owner: point; Tablespace: 
--

CREATE INDEX posts_author_idx ON posts USING btree (author) WITH (fillfactor=70);


--
-- Name: posts_author_type_idx; Type: INDEX; Schema: posts; Owner: point; Tablespace: 
--

CREATE INDEX posts_author_type_idx ON posts USING btree (author, type) WITH (fillfactor=70);


--
-- Name: posts_created_idx; Type: INDEX; Schema: posts; Owner: point; Tablespace: 
--

CREATE INDEX posts_created_idx ON posts USING btree (created DESC) WITH (fillfactor=70);


--
-- Name: posts_posts_archive_idx; Type: INDEX; Schema: posts; Owner: point; Tablespace: 
--

CREATE INDEX posts_posts_archive_idx ON posts USING btree (archive);


--
-- Name: recent_blog_created_idx; Type: INDEX; Schema: posts; Owner: point; Tablespace: 
--

CREATE INDEX recent_blog_created_idx ON recent USING btree (created DESC);


--
-- Name: recent_blog_post_id_comment_id_idx; Type: INDEX; Schema: posts; Owner: point; Tablespace: 
--

CREATE INDEX recent_blog_post_id_comment_id_idx ON recent_blog USING btree (post_id, comment_id);


--
-- Name: recent_blog_user_id_idx; Type: INDEX; Schema: posts; Owner: point; Tablespace: 
--

CREATE INDEX recent_blog_user_id_idx ON recent USING btree (user_id);


--
-- Name: recent_created_idx; Type: INDEX; Schema: posts; Owner: point; Tablespace: 
--

CREATE INDEX recent_created_idx ON recent USING btree (created DESC);


--
-- Name: recent_post_id_comment_id_idx; Type: INDEX; Schema: posts; Owner: point; Tablespace: 
--

CREATE INDEX recent_post_id_comment_id_idx ON recent USING btree (post_id, comment_id);


--
-- Name: recent_rcpt_id_idx; Type: INDEX; Schema: posts; Owner: point; Tablespace: 
--

CREATE INDEX recent_rcpt_id_idx ON recent USING btree (rcpt_id);


--
-- Name: recipients_user_id_idx; Type: INDEX; Schema: posts; Owner: point; Tablespace: 
--

CREATE INDEX recipients_user_id_idx ON recipients USING btree (user_id);


--
-- Name: recommendations_created_idx; Type: INDEX; Schema: posts; Owner: point; Tablespace: 
--

CREATE INDEX recommendations_created_idx ON recommendations USING btree (created) WITH (fillfactor=50);


--
-- Name: recommendations_post_id_comment_id_idx; Type: INDEX; Schema: posts; Owner: point; Tablespace: 
--

CREATE INDEX recommendations_post_id_comment_id_idx ON recommendations USING btree (post_id DESC, comment_id DESC) WITH (fillfactor=50);


--
-- Name: recommendations_post_id_idx; Type: INDEX; Schema: posts; Owner: point; Tablespace: 
--

CREATE INDEX recommendations_post_id_idx ON recommendations USING btree (post_id DESC) WITH (fillfactor=50);


--
-- Name: recommendations_post_id_rcid_idx; Type: INDEX; Schema: posts; Owner: point; Tablespace: 
--

CREATE INDEX recommendations_post_id_rcid_idx ON recommendations USING btree (post_id, rcid) WITH (fillfactor=50);


--
-- Name: recommendations_recv_post_id_comment_id_idx; Type: INDEX; Schema: posts; Owner: point; Tablespace: 
--

CREATE INDEX recommendations_recv_post_id_comment_id_idx ON recommendations_recv USING btree (post_id, comment_id) WITH (fillfactor=50);


--
-- Name: recommendations_recv_user_id_idx; Type: INDEX; Schema: posts; Owner: point; Tablespace: 
--

CREATE INDEX recommendations_recv_user_id_idx ON recommendations_recv USING btree (user_id) WITH (fillfactor=50);


--
-- Name: recommendations_user_id_idx; Type: INDEX; Schema: posts; Owner: point; Tablespace: 
--

CREATE INDEX recommendations_user_id_idx ON recommendations USING btree (user_id) WITH (fillfactor=50);


--
-- Name: tags_blacklist_global_lower_tag_idx; Type: INDEX; Schema: posts; Owner: point; Tablespace: 
--

CREATE INDEX tags_blacklist_global_lower_tag_idx ON tags_blacklist_global USING btree (lower(tag)) WITH (fillfactor=50);


--
-- Name: tags_blacklist_global_tag_idx; Type: INDEX; Schema: posts; Owner: point; Tablespace: 
--

CREATE INDEX tags_blacklist_global_tag_idx ON tags_blacklist_global USING btree (tag) WITH (fillfactor=50);


--
-- Name: tags_blacklist_global_user_id_idx; Type: INDEX; Schema: posts; Owner: point; Tablespace: 
--

CREATE INDEX tags_blacklist_global_user_id_idx ON tags_blacklist_global USING btree (user_id) WITH (fillfactor=50);


--
-- Name: tags_blacklist_user_tag_idx; Type: INDEX; Schema: posts; Owner: point; Tablespace: 
--

CREATE INDEX tags_blacklist_user_tag_idx ON tags_blacklist_user USING btree (tag) WITH (fillfactor=50);


--
-- Name: tags_blacklist_user_to_user_id_lower_tag_idx; Type: INDEX; Schema: posts; Owner: point; Tablespace: 
--

CREATE INDEX tags_blacklist_user_to_user_id_lower_tag_idx ON tags_blacklist_user USING btree (to_user_id, lower(tag)) WITH (fillfactor=50);


--
-- Name: tags_blacklist_user_user_id_idx; Type: INDEX; Schema: posts; Owner: point; Tablespace: 
--

CREATE INDEX tags_blacklist_user_user_id_idx ON tags_blacklist_user USING btree (user_id) WITH (fillfactor=50);


--
-- Name: tags_blacklist_user_user_id_lower_tag_idx; Type: INDEX; Schema: posts; Owner: point; Tablespace: 
--

CREATE INDEX tags_blacklist_user_user_id_lower_tag_idx ON tags_blacklist_user USING btree (user_id, lower(tag)) WITH (fillfactor=50);


--
-- Name: tags_blacklist_user_user_id_to_user_id_lower_tag_idx; Type: INDEX; Schema: posts; Owner: point; Tablespace: 
--

CREATE INDEX tags_blacklist_user_user_id_to_user_id_lower_tag_idx ON tags_blacklist_user USING btree (user_id, to_user_id, lower(tag)) WITH (fillfactor=50);


--
-- Name: tags_lower_tag; Type: INDEX; Schema: posts; Owner: point; Tablespace: 
--

CREATE INDEX tags_lower_tag ON tags USING btree (lower(tag)) WITH (fillfactor=50);


--
-- Name: tags_post_id_idx; Type: INDEX; Schema: posts; Owner: point; Tablespace: 
--

CREATE INDEX tags_post_id_idx ON tags USING btree (post_id DESC) WITH (fillfactor=50);


--
-- Name: tags_tag_idx; Type: INDEX; Schema: posts; Owner: point; Tablespace: 
--

CREATE INDEX tags_tag_idx ON tags USING btree (tag) WITH (fillfactor=50);


--
-- Name: tags_user_id_idx; Type: INDEX; Schema: posts; Owner: point; Tablespace: 
--

CREATE INDEX tags_user_id_idx ON tags USING btree (user_id) WITH (fillfactor=50);


--
-- Name: tags_user_id_lower_tag; Type: INDEX; Schema: posts; Owner: point; Tablespace: 
--

CREATE INDEX tags_user_id_lower_tag ON tags USING btree (user_id, lower(tag)) WITH (fillfactor=50);


--
-- Name: unread_comments_created_idx; Type: INDEX; Schema: posts; Owner: point; Tablespace: 
--

CREATE INDEX unread_comments_created_idx ON unread_comments USING btree (created DESC);


--
-- Name: unread_comments_user_id_created_idx; Type: INDEX; Schema: posts; Owner: point; Tablespace: 
--

CREATE INDEX unread_comments_user_id_created_idx ON unread_comments USING btree (user_id, created DESC);


--
-- Name: unread_comments_user_id_idx; Type: INDEX; Schema: posts; Owner: point; Tablespace: 
--

CREATE INDEX unread_comments_user_id_idx ON unread_comments USING btree (user_id);


--
-- Name: unread_comments_user_id_post_id_idx; Type: INDEX; Schema: posts; Owner: point; Tablespace: 
--

CREATE INDEX unread_comments_user_id_post_id_idx ON unread_comments USING btree (user_id, post_id);


--
-- Name: unread_comments_user_id_type_idx; Type: INDEX; Schema: posts; Owner: point; Tablespace: 
--

CREATE INDEX unread_comments_user_id_type_idx ON unread_comments USING btree (user_id, type);


--
-- Name: unread_posts_user_id_idx; Type: INDEX; Schema: posts; Owner: point; Tablespace: 
--

CREATE INDEX unread_posts_user_id_idx ON unread_posts USING btree (user_id);


--
-- Name: unread_posts_user_id_type_idx; Type: INDEX; Schema: posts; Owner: point; Tablespace: 
--

CREATE INDEX unread_posts_user_id_type_idx ON unread_posts USING btree (user_id, type);


SET search_path = subs, pg_catalog;

--
-- Name: posts_post_id_idx; Type: INDEX; Schema: subs; Owner: point; Tablespace: 
--

CREATE INDEX posts_post_id_idx ON posts USING btree (post_id) WITH (fillfactor=50);


--
-- Name: posts_user_id_idx; Type: INDEX; Schema: subs; Owner: point; Tablespace: 
--

CREATE INDEX posts_user_id_idx ON posts USING btree (user_id) WITH (fillfactor=50);


--
-- Name: posts_user_id_post_id_idx; Type: INDEX; Schema: subs; Owner: point; Tablespace: 
--

CREATE INDEX posts_user_id_post_id_idx ON posts USING btree (user_id, post_id) WITH (fillfactor=50);


--
-- Name: recommendations_to_user_id_idx; Type: INDEX; Schema: subs; Owner: point; Tablespace: 
--

CREATE INDEX recommendations_to_user_id_idx ON recommendations USING btree (to_user_id);


--
-- Name: recommendations_user_id_idx; Type: INDEX; Schema: subs; Owner: point; Tablespace: 
--

CREATE INDEX recommendations_user_id_idx ON recommendations USING btree (user_id);


--
-- Name: requests_to_user_id_idx; Type: INDEX; Schema: subs; Owner: point; Tablespace: 
--

CREATE INDEX requests_to_user_id_idx ON requests USING btree (to_user_id);


--
-- Name: requests_user_id_idx; Type: INDEX; Schema: subs; Owner: point; Tablespace: 
--

CREATE INDEX requests_user_id_idx ON requests USING btree (user_id);


--
-- Name: requests_user_id_to_user_id_idx; Type: INDEX; Schema: subs; Owner: point; Tablespace: 
--

CREATE INDEX requests_user_id_to_user_id_idx ON requests USING btree (user_id, to_user_id);


--
-- Name: tags_global_tag_idx; Type: INDEX; Schema: subs; Owner: point; Tablespace: 
--

CREATE INDEX tags_global_tag_idx ON tags_global USING btree (tag) WITH (fillfactor=50);


--
-- Name: tags_global_user_id_idx; Type: INDEX; Schema: subs; Owner: point; Tablespace: 
--

CREATE INDEX tags_global_user_id_idx ON tags_global USING btree (user_id) WITH (fillfactor=50);


--
-- Name: tags_global_user_id_tag_idx; Type: INDEX; Schema: subs; Owner: point; Tablespace: 
--

CREATE INDEX tags_global_user_id_tag_idx ON tags_global USING btree (user_id, tag) WITH (fillfactor=50);


--
-- Name: tags_user_tag_idx; Type: INDEX; Schema: subs; Owner: point; Tablespace: 
--

CREATE INDEX tags_user_tag_idx ON tags_user USING btree (tag) WITH (fillfactor=50);


--
-- Name: tags_user_user_id_idx; Type: INDEX; Schema: subs; Owner: point; Tablespace: 
--

CREATE INDEX tags_user_user_id_idx ON tags_user USING btree (user_id) WITH (fillfactor=50);


--
-- Name: tags_user_user_id_tag_idx; Type: INDEX; Schema: subs; Owner: point; Tablespace: 
--

CREATE INDEX tags_user_user_id_tag_idx ON tags_user USING btree (user_id, tag) WITH (fillfactor=50);


--
-- Name: tags_user_user_id_to_user_id_tag_idx; Type: INDEX; Schema: subs; Owner: point; Tablespace: 
--

CREATE INDEX tags_user_user_id_to_user_id_tag_idx ON tags_user USING btree (user_id, to_user_id, tag) WITH (fillfactor=50);


--
-- Name: users_to_user_id_idx; Type: INDEX; Schema: subs; Owner: point; Tablespace: 
--

CREATE INDEX users_to_user_id_idx ON users USING btree (to_user_id);


--
-- Name: users_user_id_idx; Type: INDEX; Schema: subs; Owner: point; Tablespace: 
--

CREATE INDEX users_user_id_idx ON users USING btree (user_id);


--
-- Name: users_user_id_to_user_id_idx; Type: INDEX; Schema: subs; Owner: point; Tablespace: 
--

CREATE INDEX users_user_id_to_user_id_idx ON users USING btree (user_id, to_user_id);


SET search_path = users, pg_catalog;

--
-- Name: accounts_address_idx; Type: INDEX; Schema: users; Owner: point; Tablespace: 
--

CREATE INDEX accounts_address_idx ON accounts USING btree (address);


--
-- Name: accounts_type_address_idx; Type: INDEX; Schema: users; Owner: point; Tablespace: 
--

CREATE UNIQUE INDEX accounts_type_address_idx ON accounts USING btree (type, address);


--
-- Name: accounts_unconfirmed_address_idx; Type: INDEX; Schema: users; Owner: point; Tablespace: 
--

CREATE INDEX accounts_unconfirmed_address_idx ON accounts_unconfirmed USING btree (address);


--
-- Name: accounts_unconfirmed_code_idx; Type: INDEX; Schema: users; Owner: point; Tablespace: 
--

CREATE INDEX accounts_unconfirmed_code_idx ON accounts_unconfirmed USING btree (code);


--
-- Name: accounts_unconfirmed_type_address_idx; Type: INDEX; Schema: users; Owner: point; Tablespace: 
--

CREATE UNIQUE INDEX accounts_unconfirmed_type_address_idx ON accounts_unconfirmed USING btree (type, address);


--
-- Name: accounts_unconfirmed_user_id_idx; Type: INDEX; Schema: users; Owner: point; Tablespace: 
--

CREATE INDEX accounts_unconfirmed_user_id_idx ON accounts_unconfirmed USING btree (user_id);


--
-- Name: accounts_unconfirmed_user_id_type_idx; Type: INDEX; Schema: users; Owner: point; Tablespace: 
--

CREATE INDEX accounts_unconfirmed_user_id_type_idx ON accounts_unconfirmed USING btree (user_id, type);


--
-- Name: accounts_user_id_idx; Type: INDEX; Schema: users; Owner: point; Tablespace: 
--

CREATE INDEX accounts_user_id_idx ON accounts USING btree (user_id);


--
-- Name: accounts_user_id_type_idx; Type: INDEX; Schema: users; Owner: point; Tablespace: 
--

CREATE INDEX accounts_user_id_type_idx ON accounts USING btree (user_id, type);


--
-- Name: aliases_alias_idx; Type: INDEX; Schema: users; Owner: point; Tablespace: 
--

CREATE INDEX aliases_alias_idx ON aliases USING btree (lower((alias)::text));


--
-- Name: blacklist_to_user_id_idx; Type: INDEX; Schema: users; Owner: point; Tablespace: 
--

CREATE INDEX blacklist_to_user_id_idx ON blacklist USING btree (to_user_id);


--
-- Name: blacklist_user_id_idx; Type: INDEX; Schema: users; Owner: point; Tablespace: 
--

CREATE INDEX blacklist_user_id_idx ON blacklist USING btree (user_id);


--
-- Name: domains_domain_idx; Type: INDEX; Schema: users; Owner: point; Tablespace: 
--

CREATE UNIQUE INDEX domains_domain_idx ON domains USING btree (domain);


--
-- Name: domains_id_idx; Type: INDEX; Schema: users; Owner: point; Tablespace: 
--

CREATE INDEX domains_id_idx ON domains USING btree (id);


--
-- Name: info_email_idx; Type: INDEX; Schema: users; Owner: point; Tablespace: 
--

CREATE INDEX info_email_idx ON info USING btree (email);


--
-- Name: profile_im_highlight_idx; Type: INDEX; Schema: users; Owner: point; Tablespace: 
--

CREATE INDEX profile_im_highlight_idx ON profile_im USING btree (highlight);


--
-- Name: ulogin_accounts_id_idx; Type: INDEX; Schema: users; Owner: point; Tablespace: 
--

CREATE INDEX ulogin_accounts_id_idx ON ulogin_accounts USING btree (id);


--
-- Name: ulogin_accounts_id_network_uid_idx; Type: INDEX; Schema: users; Owner: point; Tablespace: 
--

CREATE INDEX ulogin_accounts_id_network_uid_idx ON ulogin_accounts USING btree (id, network, uid);


--
-- Name: user_aliases_alias_idx; Type: INDEX; Schema: users; Owner: point; Tablespace: 
--

CREATE INDEX user_aliases_alias_idx ON user_aliases USING btree (lower((alias)::text));


--
-- Name: user_aliases_user_id_alias_idx; Type: INDEX; Schema: users; Owner: point; Tablespace: 
--

CREATE INDEX user_aliases_user_id_alias_idx ON user_aliases USING btree (user_id, lower((alias)::text));


--
-- Name: users_lower_login_idx; Type: INDEX; Schema: users; Owner: point; Tablespace: 
--

CREATE INDEX users_lower_login_idx ON logins USING btree (lower((login)::text));


--
-- Name: whitelist_to_user_id_idx; Type: INDEX; Schema: users; Owner: point; Tablespace: 
--

CREATE INDEX whitelist_to_user_id_idx ON whitelist USING btree (to_user_id);


--
-- Name: whitelist_user_id_idx; Type: INDEX; Schema: users; Owner: point; Tablespace: 
--

CREATE INDEX whitelist_user_id_idx ON whitelist USING btree (user_id);


SET search_path = posts, pg_catalog;

--
-- Name: comment_before_delete_trg; Type: TRIGGER; Schema: posts; Owner: point
--

CREATE TRIGGER comment_before_delete_trg BEFORE DELETE ON comments FOR EACH ROW EXECUTE PROCEDURE public.comment_delete();


--
-- Name: post_recent_after_insert_trg; Type: TRIGGER; Schema: posts; Owner: point
--

CREATE TRIGGER post_recent_after_insert_trg AFTER INSERT ON posts FOR EACH ROW EXECUTE PROCEDURE insert_post_recent();


--
-- Name: recommendation_recent_after_insert_trg; Type: TRIGGER; Schema: posts; Owner: point
--

CREATE TRIGGER recommendation_recent_after_insert_trg AFTER INSERT ON recommendations FOR EACH ROW EXECUTE PROCEDURE insert_recommendation_recent();


--
-- Name: recommendation_recent_before_delete_trg; Type: TRIGGER; Schema: posts; Owner: point
--

CREATE TRIGGER recommendation_recent_before_delete_trg BEFORE DELETE ON recommendations FOR EACH ROW EXECUTE PROCEDURE delete_recommendation_recent();


--
-- Name: tags_blacklist_before_insert_trg; Type: TRIGGER; Schema: posts; Owner: point
--

CREATE TRIGGER tags_blacklist_before_insert_trg BEFORE INSERT ON tags_blacklist FOR EACH ROW EXECUTE PROCEDURE insert_tags_blacklist();


SET search_path = subs, pg_catalog;

--
-- Name: tags_before_insert_trg; Type: TRIGGER; Schema: subs; Owner: point
--

CREATE TRIGGER tags_before_insert_trg BEFORE INSERT ON tags FOR EACH ROW EXECUTE PROCEDURE insert_tags();


SET search_path = posts, pg_catalog;

--
-- Name: bookmarks_post_id_fkey; Type: FK CONSTRAINT; Schema: posts; Owner: point
--

ALTER TABLE ONLY bookmarks
    ADD CONSTRAINT bookmarks_post_id_fkey FOREIGN KEY (post_id) REFERENCES posts(id) ON UPDATE CASCADE ON DELETE CASCADE DEFERRABLE;


--
-- Name: bookmarks_user_id_fkey; Type: FK CONSTRAINT; Schema: posts; Owner: point
--

ALTER TABLE ONLY bookmarks
    ADD CONSTRAINT bookmarks_user_id_fkey FOREIGN KEY (user_id) REFERENCES users.logins(id) ON UPDATE CASCADE ON DELETE CASCADE DEFERRABLE;


--
-- Name: comments_author_fkey; Type: FK CONSTRAINT; Schema: posts; Owner: point
--

ALTER TABLE ONLY comments
    ADD CONSTRAINT comments_author_fkey FOREIGN KEY (author) REFERENCES users.logins(id) ON UPDATE CASCADE ON DELETE CASCADE DEFERRABLE;


--
-- Name: comments_post_id_fkey; Type: FK CONSTRAINT; Schema: posts; Owner: point
--

ALTER TABLE ONLY comments
    ADD CONSTRAINT comments_post_id_fkey FOREIGN KEY (post_id) REFERENCES posts(id) ON UPDATE CASCADE ON DELETE CASCADE DEFERRABLE;


--
-- Name: comments_to_user_fkey; Type: FK CONSTRAINT; Schema: posts; Owner: point
--

ALTER TABLE ONLY comments
    ADD CONSTRAINT comments_to_user_fkey FOREIGN KEY (to_user_id) REFERENCES users.logins(id) ON UPDATE CASCADE DEFERRABLE;


--
-- Name: posts_author_fkey; Type: FK CONSTRAINT; Schema: posts; Owner: point
--

ALTER TABLE ONLY posts
    ADD CONSTRAINT posts_author_fkey FOREIGN KEY (author) REFERENCES users.logins(id) ON UPDATE CASCADE ON DELETE CASCADE DEFERRABLE;


--
-- Name: recent_blog_post_id_fkey; Type: FK CONSTRAINT; Schema: posts; Owner: point
--

ALTER TABLE ONLY recent_blog
    ADD CONSTRAINT recent_blog_post_id_fkey FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE;


--
-- Name: recent_blog_user_id_fkey; Type: FK CONSTRAINT; Schema: posts; Owner: point
--

ALTER TABLE ONLY recent_blog
    ADD CONSTRAINT recent_blog_user_id_fkey FOREIGN KEY (user_id) REFERENCES users.logins(id) ON DELETE CASCADE;


--
-- Name: recent_post_id_fkey; Type: FK CONSTRAINT; Schema: posts; Owner: point
--

ALTER TABLE ONLY recent
    ADD CONSTRAINT recent_post_id_fkey FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE;


--
-- Name: recent_rcpt_id_fkey; Type: FK CONSTRAINT; Schema: posts; Owner: point
--

ALTER TABLE ONLY recent
    ADD CONSTRAINT recent_rcpt_id_fkey FOREIGN KEY (rcpt_id) REFERENCES users.logins(id) ON DELETE CASCADE;


--
-- Name: recent_user_id_fkey; Type: FK CONSTRAINT; Schema: posts; Owner: point
--

ALTER TABLE ONLY recent
    ADD CONSTRAINT recent_user_id_fkey FOREIGN KEY (user_id) REFERENCES users.logins(id) ON DELETE CASCADE;


--
-- Name: recipients_post_id_fkey; Type: FK CONSTRAINT; Schema: posts; Owner: point
--

ALTER TABLE ONLY recipients
    ADD CONSTRAINT recipients_post_id_fkey FOREIGN KEY (post_id) REFERENCES posts(id) ON UPDATE CASCADE ON DELETE CASCADE DEFERRABLE;


--
-- Name: recipients_user_id_fkey; Type: FK CONSTRAINT; Schema: posts; Owner: point
--

ALTER TABLE ONLY recipients
    ADD CONSTRAINT recipients_user_id_fkey FOREIGN KEY (user_id) REFERENCES users.logins(id) ON UPDATE CASCADE ON DELETE CASCADE DEFERRABLE;


--
-- Name: recommendations_post_id_fkey; Type: FK CONSTRAINT; Schema: posts; Owner: point
--

ALTER TABLE ONLY recommendations
    ADD CONSTRAINT recommendations_post_id_fkey FOREIGN KEY (post_id) REFERENCES posts(id) ON UPDATE CASCADE ON DELETE CASCADE DEFERRABLE;


--
-- Name: recommendations_recv_post_id_fkey; Type: FK CONSTRAINT; Schema: posts; Owner: point
--

ALTER TABLE ONLY recommendations_recv
    ADD CONSTRAINT recommendations_recv_post_id_fkey FOREIGN KEY (post_id) REFERENCES posts(id) ON UPDATE CASCADE ON DELETE CASCADE DEFERRABLE;


--
-- Name: recommendations_recv_user_id_fkey; Type: FK CONSTRAINT; Schema: posts; Owner: point
--

ALTER TABLE ONLY recommendations_recv
    ADD CONSTRAINT recommendations_recv_user_id_fkey FOREIGN KEY (user_id) REFERENCES users.logins(id) ON UPDATE CASCADE ON DELETE CASCADE DEFERRABLE;


--
-- Name: recommendations_user_id_fkey; Type: FK CONSTRAINT; Schema: posts; Owner: point
--

ALTER TABLE ONLY recommendations
    ADD CONSTRAINT recommendations_user_id_fkey FOREIGN KEY (user_id) REFERENCES users.logins(id) ON UPDATE CASCADE ON DELETE CASCADE DEFERRABLE;


--
-- Name: tags_blacklist_to_user_id_fkey; Type: FK CONSTRAINT; Schema: posts; Owner: point
--

ALTER TABLE ONLY tags_blacklist
    ADD CONSTRAINT tags_blacklist_to_user_id_fkey FOREIGN KEY (to_user_id) REFERENCES users.logins(id) ON UPDATE CASCADE ON DELETE CASCADE DEFERRABLE;


--
-- Name: tags_blacklist_user_id_fkey; Type: FK CONSTRAINT; Schema: posts; Owner: point
--

ALTER TABLE ONLY tags_blacklist
    ADD CONSTRAINT tags_blacklist_user_id_fkey FOREIGN KEY (user_id) REFERENCES users.logins(id) ON UPDATE CASCADE ON DELETE CASCADE DEFERRABLE;


--
-- Name: tags_post_id_fkey; Type: FK CONSTRAINT; Schema: posts; Owner: point
--

ALTER TABLE ONLY tags
    ADD CONSTRAINT tags_post_id_fkey FOREIGN KEY (post_id) REFERENCES posts(id) ON UPDATE CASCADE ON DELETE CASCADE DEFERRABLE;


--
-- Name: tags_user_id_fkey; Type: FK CONSTRAINT; Schema: posts; Owner: point
--

ALTER TABLE ONLY tags
    ADD CONSTRAINT tags_user_id_fkey FOREIGN KEY (user_id) REFERENCES users.logins(id) ON UPDATE CASCADE ON DELETE CASCADE DEFERRABLE;


--
-- Name: unread_comments_post_id_comment_id_fkey; Type: FK CONSTRAINT; Schema: posts; Owner: point
--

ALTER TABLE ONLY unread_comments
    ADD CONSTRAINT unread_comments_post_id_comment_id_fkey FOREIGN KEY (post_id, comment_id) REFERENCES comments(post_id, comment_id) ON DELETE CASCADE;


--
-- Name: unread_comments_post_id_fkey; Type: FK CONSTRAINT; Schema: posts; Owner: point
--

ALTER TABLE ONLY unread_comments
    ADD CONSTRAINT unread_comments_post_id_fkey FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE;


--
-- Name: unread_comments_user_id_fkey; Type: FK CONSTRAINT; Schema: posts; Owner: point
--

ALTER TABLE ONLY unread_comments
    ADD CONSTRAINT unread_comments_user_id_fkey FOREIGN KEY (user_id) REFERENCES users.logins(id) ON DELETE CASCADE;


--
-- Name: unread_posts_post_id_fkey; Type: FK CONSTRAINT; Schema: posts; Owner: point
--

ALTER TABLE ONLY unread_posts
    ADD CONSTRAINT unread_posts_post_id_fkey FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE;


--
-- Name: unread_posts_user_id_fkey; Type: FK CONSTRAINT; Schema: posts; Owner: point
--

ALTER TABLE ONLY unread_posts
    ADD CONSTRAINT unread_posts_user_id_fkey FOREIGN KEY (user_id) REFERENCES users.logins(id) ON DELETE CASCADE;


--
-- Name: updates_post_id_fkey; Type: FK CONSTRAINT; Schema: posts; Owner: point
--

ALTER TABLE ONLY updates
    ADD CONSTRAINT updates_post_id_fkey FOREIGN KEY (post_id) REFERENCES posts(id) ON UPDATE CASCADE ON DELETE CASCADE DEFERRABLE;


SET search_path = subs, pg_catalog;

--
-- Name: posts_user_id_fkey; Type: FK CONSTRAINT; Schema: subs; Owner: point
--

ALTER TABLE ONLY posts
    ADD CONSTRAINT posts_user_id_fkey FOREIGN KEY (user_id) REFERENCES users.logins(id) ON UPDATE CASCADE ON DELETE CASCADE DEFERRABLE;


--
-- Name: recommendations_to_user_id_fkey; Type: FK CONSTRAINT; Schema: subs; Owner: point
--

ALTER TABLE ONLY recommendations
    ADD CONSTRAINT recommendations_to_user_id_fkey FOREIGN KEY (to_user_id) REFERENCES users.logins(id) ON UPDATE CASCADE ON DELETE CASCADE DEFERRABLE;


--
-- Name: recommendations_user_id_fkey; Type: FK CONSTRAINT; Schema: subs; Owner: point
--

ALTER TABLE ONLY recommendations
    ADD CONSTRAINT recommendations_user_id_fkey FOREIGN KEY (user_id) REFERENCES users.logins(id) ON UPDATE CASCADE ON DELETE CASCADE DEFERRABLE;


--
-- Name: requests_to_user_id_fkey; Type: FK CONSTRAINT; Schema: subs; Owner: point
--

ALTER TABLE ONLY requests
    ADD CONSTRAINT requests_to_user_id_fkey FOREIGN KEY (to_user_id) REFERENCES users.logins(id) ON UPDATE CASCADE ON DELETE CASCADE DEFERRABLE;


--
-- Name: requests_user_id_fkey; Type: FK CONSTRAINT; Schema: subs; Owner: point
--

ALTER TABLE ONLY requests
    ADD CONSTRAINT requests_user_id_fkey FOREIGN KEY (user_id) REFERENCES users.logins(id) ON UPDATE CASCADE ON DELETE CASCADE DEFERRABLE;


--
-- Name: tags_to_user_id_fkey; Type: FK CONSTRAINT; Schema: subs; Owner: point
--

ALTER TABLE ONLY tags
    ADD CONSTRAINT tags_to_user_id_fkey FOREIGN KEY (to_user_id) REFERENCES users.logins(id) ON UPDATE CASCADE ON DELETE CASCADE DEFERRABLE;


--
-- Name: tags_user_id_fkey; Type: FK CONSTRAINT; Schema: subs; Owner: point
--

ALTER TABLE ONLY tags
    ADD CONSTRAINT tags_user_id_fkey FOREIGN KEY (user_id) REFERENCES users.logins(id) ON UPDATE CASCADE ON DELETE CASCADE DEFERRABLE;


--
-- Name: users_to_user_id_fkey; Type: FK CONSTRAINT; Schema: subs; Owner: point
--

ALTER TABLE ONLY users
    ADD CONSTRAINT users_to_user_id_fkey FOREIGN KEY (to_user_id) REFERENCES users.logins(id) ON UPDATE CASCADE ON DELETE CASCADE DEFERRABLE;


--
-- Name: users_user_id_fkey; Type: FK CONSTRAINT; Schema: subs; Owner: point
--

ALTER TABLE ONLY users
    ADD CONSTRAINT users_user_id_fkey FOREIGN KEY (user_id) REFERENCES users.logins(id) ON UPDATE CASCADE ON DELETE CASCADE DEFERRABLE;


SET search_path = users, pg_catalog;

--
-- Name: accounts_user_id_fkey; Type: FK CONSTRAINT; Schema: users; Owner: point
--

ALTER TABLE ONLY accounts
    ADD CONSTRAINT accounts_user_id_fkey FOREIGN KEY (user_id) REFERENCES logins(id) ON UPDATE CASCADE ON DELETE CASCADE DEFERRABLE;


--
-- Name: accounts_user_id_fkey; Type: FK CONSTRAINT; Schema: users; Owner: point
--

ALTER TABLE ONLY accounts_unconfirmed
    ADD CONSTRAINT accounts_user_id_fkey FOREIGN KEY (user_id) REFERENCES logins(id) ON UPDATE CASCADE ON DELETE CASCADE DEFERRABLE;


--
-- Name: blacklist_to_user_id_fkey; Type: FK CONSTRAINT; Schema: users; Owner: point
--

ALTER TABLE ONLY blacklist
    ADD CONSTRAINT blacklist_to_user_id_fkey FOREIGN KEY (to_user_id) REFERENCES logins(id) ON UPDATE CASCADE ON DELETE CASCADE DEFERRABLE;


--
-- Name: blacklist_user_id_fkey; Type: FK CONSTRAINT; Schema: users; Owner: point
--

ALTER TABLE ONLY blacklist
    ADD CONSTRAINT blacklist_user_id_fkey FOREIGN KEY (user_id) REFERENCES logins(id) ON UPDATE CASCADE ON DELETE CASCADE DEFERRABLE;


--
-- Name: domains_id_fkey; Type: FK CONSTRAINT; Schema: users; Owner: point
--

ALTER TABLE ONLY domains
    ADD CONSTRAINT domains_id_fkey FOREIGN KEY (id) REFERENCES logins(id) ON UPDATE CASCADE ON DELETE CASCADE DEFERRABLE;


--
-- Name: feeds_id_fkey; Type: FK CONSTRAINT; Schema: users; Owner: point
--

ALTER TABLE ONLY feeds
    ADD CONSTRAINT feeds_id_fkey FOREIGN KEY (id) REFERENCES logins(id) ON UPDATE CASCADE ON DELETE CASCADE DEFERRABLE;


--
-- Name: info_id_fkey; Type: FK CONSTRAINT; Schema: users; Owner: point
--

ALTER TABLE ONLY info
    ADD CONSTRAINT info_id_fkey FOREIGN KEY (id) REFERENCES logins(id) ON UPDATE CASCADE ON DELETE CASCADE DEFERRABLE;


--
-- Name: profile_id_fkey; Type: FK CONSTRAINT; Schema: users; Owner: point
--

ALTER TABLE ONLY profile
    ADD CONSTRAINT profile_id_fkey FOREIGN KEY (id) REFERENCES logins(id) ON UPDATE CASCADE ON DELETE CASCADE DEFERRABLE;


--
-- Name: profile_im_id_fkey; Type: FK CONSTRAINT; Schema: users; Owner: point
--

ALTER TABLE ONLY profile_im
    ADD CONSTRAINT profile_im_id_fkey FOREIGN KEY (id) REFERENCES logins(id) ON UPDATE CASCADE ON DELETE CASCADE DEFERRABLE;


--
-- Name: ulogin_accounts_id_fkey; Type: FK CONSTRAINT; Schema: users; Owner: point
--

ALTER TABLE ONLY ulogin_accounts
    ADD CONSTRAINT ulogin_accounts_id_fkey FOREIGN KEY (id) REFERENCES logins(id) ON UPDATE CASCADE ON DELETE CASCADE DEFERRABLE;


--
-- Name: whitelist_to_user_id_fkey; Type: FK CONSTRAINT; Schema: users; Owner: point
--

ALTER TABLE ONLY whitelist
    ADD CONSTRAINT whitelist_to_user_id_fkey FOREIGN KEY (to_user_id) REFERENCES logins(id) ON UPDATE CASCADE ON DELETE CASCADE DEFERRABLE;


--
-- Name: whitelist_user_id_fkey; Type: FK CONSTRAINT; Schema: users; Owner: point
--

ALTER TABLE ONLY whitelist
    ADD CONSTRAINT whitelist_user_id_fkey FOREIGN KEY (user_id) REFERENCES logins(id) ON UPDATE CASCADE ON DELETE CASCADE DEFERRABLE;


--
-- Name: posts; Type: ACL; Schema: -; Owner: point
--

REVOKE ALL ON SCHEMA posts FROM PUBLIC;
REVOKE ALL ON SCHEMA posts FROM point;
GRANT ALL ON SCHEMA posts TO point;


--
-- Name: public; Type: ACL; Schema: -; Owner: postgres
--

REVOKE ALL ON SCHEMA public FROM PUBLIC;
REVOKE ALL ON SCHEMA public FROM postgres;
GRANT ALL ON SCHEMA public TO postgres;
GRANT ALL ON SCHEMA public TO PUBLIC;


--
-- Name: users; Type: ACL; Schema: -; Owner: point
--

REVOKE ALL ON SCHEMA users FROM PUBLIC;
REVOKE ALL ON SCHEMA users FROM point;
GRANT ALL ON SCHEMA users TO point;


SET search_path = posts, pg_catalog;

--
-- Name: comments; Type: ACL; Schema: posts; Owner: point
--

REVOKE ALL ON TABLE comments FROM PUBLIC;
REVOKE ALL ON TABLE comments FROM point;
GRANT ALL ON TABLE comments TO point;


--
-- Name: comments_id_seq; Type: ACL; Schema: posts; Owner: point
--

REVOKE ALL ON SEQUENCE comments_id_seq FROM PUBLIC;
REVOKE ALL ON SEQUENCE comments_id_seq FROM point;
GRANT ALL ON SEQUENCE comments_id_seq TO point;


--
-- Name: posts; Type: ACL; Schema: posts; Owner: point
--

REVOKE ALL ON TABLE posts FROM PUBLIC;
REVOKE ALL ON TABLE posts FROM point;
GRANT ALL ON TABLE posts TO point;


--
-- Name: posts_id_seq; Type: ACL; Schema: posts; Owner: point
--

REVOKE ALL ON SEQUENCE posts_id_seq FROM PUBLIC;
REVOKE ALL ON SEQUENCE posts_id_seq FROM point;
GRANT ALL ON SEQUENCE posts_id_seq TO point;


--
-- Name: recent; Type: ACL; Schema: posts; Owner: point
--

REVOKE ALL ON TABLE recent FROM PUBLIC;
REVOKE ALL ON TABLE recent FROM point;
GRANT ALL ON TABLE recent TO point;


--
-- Name: recent_blog; Type: ACL; Schema: posts; Owner: point
--

REVOKE ALL ON TABLE recent_blog FROM PUBLIC;
REVOKE ALL ON TABLE recent_blog FROM point;
GRANT ALL ON TABLE recent_blog TO point;


--
-- Name: recent_blog_id_seq; Type: ACL; Schema: posts; Owner: point
--

REVOKE ALL ON SEQUENCE recent_blog_id_seq FROM PUBLIC;
REVOKE ALL ON SEQUENCE recent_blog_id_seq FROM point;
GRANT ALL ON SEQUENCE recent_blog_id_seq TO point;


--
-- Name: recent_id_seq; Type: ACL; Schema: posts; Owner: point
--

REVOKE ALL ON SEQUENCE recent_id_seq FROM PUBLIC;
REVOKE ALL ON SEQUENCE recent_id_seq FROM point;
GRANT ALL ON SEQUENCE recent_id_seq TO point;


--
-- Name: recipients; Type: ACL; Schema: posts; Owner: point
--

REVOKE ALL ON TABLE recipients FROM PUBLIC;
REVOKE ALL ON TABLE recipients FROM point;
GRANT ALL ON TABLE recipients TO point;


--
-- Name: recommendations; Type: ACL; Schema: posts; Owner: point
--

REVOKE ALL ON TABLE recommendations FROM PUBLIC;
REVOKE ALL ON TABLE recommendations FROM point;
GRANT ALL ON TABLE recommendations TO point;


--
-- Name: recommendations_recv; Type: ACL; Schema: posts; Owner: point
--

REVOKE ALL ON TABLE recommendations_recv FROM PUBLIC;
REVOKE ALL ON TABLE recommendations_recv FROM point;
GRANT ALL ON TABLE recommendations_recv TO point;


--
-- Name: tags; Type: ACL; Schema: posts; Owner: point
--

REVOKE ALL ON TABLE tags FROM PUBLIC;
REVOKE ALL ON TABLE tags FROM point;
GRANT ALL ON TABLE tags TO point;


--
-- Name: tags_blacklist; Type: ACL; Schema: posts; Owner: point
--

REVOKE ALL ON TABLE tags_blacklist FROM PUBLIC;
REVOKE ALL ON TABLE tags_blacklist FROM point;
GRANT ALL ON TABLE tags_blacklist TO point;


--
-- Name: tags_blacklist_global; Type: ACL; Schema: posts; Owner: point
--

REVOKE ALL ON TABLE tags_blacklist_global FROM PUBLIC;
REVOKE ALL ON TABLE tags_blacklist_global FROM point;
GRANT ALL ON TABLE tags_blacklist_global TO point;


--
-- Name: tags_blacklist_user; Type: ACL; Schema: posts; Owner: point
--

REVOKE ALL ON TABLE tags_blacklist_user FROM PUBLIC;
REVOKE ALL ON TABLE tags_blacklist_user FROM point;
GRANT ALL ON TABLE tags_blacklist_user TO point;


--
-- Name: updates; Type: ACL; Schema: posts; Owner: point
--

REVOKE ALL ON TABLE updates FROM PUBLIC;
REVOKE ALL ON TABLE updates FROM point;
GRANT ALL ON TABLE updates TO point;


SET search_path = users, pg_catalog;

--
-- Name: accounts; Type: ACL; Schema: users; Owner: point
--

REVOKE ALL ON TABLE accounts FROM PUBLIC;
REVOKE ALL ON TABLE accounts FROM point;
GRANT ALL ON TABLE accounts TO point;


--
-- Name: accounts_id_seq; Type: ACL; Schema: users; Owner: point
--

REVOKE ALL ON SEQUENCE accounts_id_seq FROM PUBLIC;
REVOKE ALL ON SEQUENCE accounts_id_seq FROM point;
GRANT ALL ON SEQUENCE accounts_id_seq TO point;


--
-- Name: blacklist; Type: ACL; Schema: users; Owner: point
--

REVOKE ALL ON TABLE blacklist FROM PUBLIC;
REVOKE ALL ON TABLE blacklist FROM point;
GRANT ALL ON TABLE blacklist TO point;


--
-- Name: domains; Type: ACL; Schema: users; Owner: point
--

REVOKE ALL ON TABLE domains FROM PUBLIC;
REVOKE ALL ON TABLE domains FROM point;
GRANT ALL ON TABLE domains TO point;


--
-- Name: info; Type: ACL; Schema: users; Owner: point
--

REVOKE ALL ON TABLE info FROM PUBLIC;
REVOKE ALL ON TABLE info FROM point;
GRANT ALL ON TABLE info TO point;


--
-- Name: logins; Type: ACL; Schema: users; Owner: point
--

REVOKE ALL ON TABLE logins FROM PUBLIC;
REVOKE ALL ON TABLE logins FROM point;
GRANT ALL ON TABLE logins TO point;


--
-- Name: logins_id_seq; Type: ACL; Schema: users; Owner: point
--

REVOKE ALL ON SEQUENCE logins_id_seq FROM PUBLIC;
REVOKE ALL ON SEQUENCE logins_id_seq FROM point;
GRANT ALL ON SEQUENCE logins_id_seq TO point;


--
-- Name: profile; Type: ACL; Schema: users; Owner: point
--

REVOKE ALL ON TABLE profile FROM PUBLIC;
REVOKE ALL ON TABLE profile FROM point;
GRANT ALL ON TABLE profile TO point;


--
-- Name: profile_im; Type: ACL; Schema: users; Owner: point
--

REVOKE ALL ON TABLE profile_im FROM PUBLIC;
REVOKE ALL ON TABLE profile_im FROM point;
GRANT ALL ON TABLE profile_im TO point;


--
-- Name: profile_www; Type: ACL; Schema: users; Owner: point
--

REVOKE ALL ON TABLE profile_www FROM PUBLIC;
REVOKE ALL ON TABLE profile_www FROM point;
GRANT ALL ON TABLE profile_www TO point;


--
-- Name: whitelist; Type: ACL; Schema: users; Owner: point
--

REVOKE ALL ON TABLE whitelist FROM PUBLIC;
REVOKE ALL ON TABLE whitelist FROM point;
GRANT ALL ON TABLE whitelist TO point;


--
-- PostgreSQL database dump complete
--

