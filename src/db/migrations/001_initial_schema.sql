CREATE TABLE IF NOT EXISTS schema_migrations (
    version TEXT PRIMARY KEY,
    applied_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS servers (
    id          TEXT PRIMARY KEY,        -- Discord server ID
    name        TEXT NOT NULL,
    data_source TEXT DEFAULT 'discord',   -- discord, reddit
    first_scan  TEXT,
    last_scan   TEXT,
    total_messages INTEGER DEFAULT 0,
    total_users INTEGER DEFAULT 0,
    created_at  TEXT DEFAULT (datetime('now')),
    updated_at  TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS channels (
    id              TEXT PRIMARY KEY,     -- Discord channel ID
    server_id       TEXT NOT NULL REFERENCES servers(id),
    name            TEXT NOT NULL,
    topic           TEXT,
    first_scan      TEXT,
    last_scan       TEXT,
    last_message_ts TEXT,                 -- Timestamp of last message scanned (for incremental exports)
    message_count   INTEGER DEFAULT 0,
    status          TEXT DEFAULT 'active', -- active, paused, removed
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS users (
    id                TEXT PRIMARY KEY,   -- Discord user ID
    display_name      TEXT,
    username          TEXT,
    role              TEXT DEFAULT 'unknown', -- riipstone_team, moderator, power_user, active_user, casual, unknown
    messages          INTEGER DEFAULT 0,
    reactions_given   INTEGER DEFAULT 0,
    reactions_received INTEGER DEFAULT 0,
    first_seen        TEXT,
    last_seen         TEXT,
    sentiment         TEXT,                -- positive, neutral, negative, mixed
    notes             TEXT,
    created_at        TEXT DEFAULT (datetime('now')),
    updated_at        TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS messages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id  TEXT,                      -- Original platform message ID
    channel_id  TEXT NOT NULL REFERENCES channels(id),
    user_id     TEXT NOT NULL REFERENCES users(id),
    content     TEXT,
    timestamp   TEXT,
    reply_to    TEXT,                      -- Message ID of reply target
    reactions   INTEGER DEFAULT 0,
    export_batch TEXT,                     -- Export batch identifier
    platform    TEXT DEFAULT 'discord',    -- discord, reddit
    created_at  TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS exports (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    server_id   TEXT REFERENCES servers(id),
    channel_id  TEXT REFERENCES channels(id),
    export_ts   TEXT,                      -- Timestamp when export started
    messages    INTEGER DEFAULT 0,
    new_users   INTEGER DEFAULT 0,
    duration_s  REAL,
    status      TEXT DEFAULT 'completed',  -- running, completed, failed
    notes       TEXT,
    created_at  TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS cross_references (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     TEXT NOT NULL,
    platform1   TEXT NOT NULL,              -- discord, reddit, twitter, etc.
    username1   TEXT NOT NULL,
    platform2   TEXT NOT NULL,
    username2   TEXT NOT NULL,
    match_type  TEXT,                       -- exact, fuzzy, partial
    confidence  REAL,
    created_at  TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS topics (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE,
    category    TEXT,                       -- feature_request, bug, question, feedback
    mention_count INTEGER DEFAULT 0,
    first_seen  TEXT,
    last_seen   TEXT,
    created_at  TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_messages_channel ON messages(channel_id);
CREATE INDEX IF NOT EXISTS idx_messages_user ON messages(user_id);
CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp);
CREATE INDEX IF NOT EXISTS idx_users_last_seen ON users(last_seen);
CREATE INDEX IF NOT EXISTS idx_channels_server ON channels(server_id);