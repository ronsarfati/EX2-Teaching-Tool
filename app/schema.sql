-- F1 attendance schema (design section 5). Idempotent: safe to run at every start-up.
-- Privacy (D21, FR-1.3): no name, ID, e-mail, IP address, photo or video column anywhere.

CREATE TABLE IF NOT EXISTS attendance_session (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    opened_at     REAL    NOT NULL,
    closed_at     REAL,                                  -- NULL while open
    is_open       INTEGER NOT NULL DEFAULT 1 CHECK (is_open IN (0, 1)),
    head_count    INTEGER,                               -- NULL until a photo was counted
    head_count_at REAL
);
-- At most one open session at a time (D27), enforced by the database as defence in depth.
CREATE UNIQUE INDEX IF NOT EXISTS one_open_session ON attendance_session(is_open) WHERE is_open = 1;

-- A device is a random cookie token (D6); the nickname is not unique and not personal.
CREATE TABLE IF NOT EXISTS device (
    device_token TEXT PRIMARY KEY,
    nickname     TEXT NOT NULL,
    created_at   REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS check_in (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id    INTEGER NOT NULL REFERENCES attendance_session(id),
    device_token  TEXT    NOT NULL REFERENCES device(device_token),
    nickname      TEXT    NOT NULL,                      -- copy at check-in time
    checked_in_at REAL    NOT NULL,
    UNIQUE (session_id, device_token)                    -- one check-in per device per session (FR-1.12)
);

CREATE TABLE IF NOT EXISTS checkin_window (
    session_id   INTEGER NOT NULL REFERENCES attendance_session(id),
    device_token TEXT    NOT NULL,
    opened_at    REAL    NOT NULL,
    attempts     INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (session_id, device_token)
);

-- Lecturer-edited list: kind is 'peer_repo' (kept generic).
CREATE TABLE IF NOT EXISTS setting_item (
    kind  TEXT NOT NULL,
    value TEXT NOT NULL,
    PRIMARY KEY (kind, value)
);

-- F3 polls (D9, D28). Anonymous: a vote stores the random device token only, never a nickname or an IP (D21).
CREATE TABLE IF NOT EXISTS poll (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    question   TEXT    NOT NULL,
    is_open    INTEGER NOT NULL DEFAULT 1 CHECK (is_open IN (0, 1)),
    created_at REAL    NOT NULL,
    closed_at  REAL
);
-- At most one open poll at a time (D28), enforced by the database as defence in depth.
CREATE UNIQUE INDEX IF NOT EXISTS one_open_poll ON poll(is_open) WHERE is_open = 1;

CREATE TABLE IF NOT EXISTS poll_option (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    poll_id  INTEGER NOT NULL REFERENCES poll(id),
    position INTEGER NOT NULL CHECK (position BETWEEN 1 AND 4),
    label    TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS vote (
    poll_id      INTEGER NOT NULL REFERENCES poll(id),
    device_token TEXT    NOT NULL,                       -- no FK: voting needs no nickname (D28)
    option_id    INTEGER NOT NULL REFERENCES poll_option(id),
    voted_at     REAL    NOT NULL,
    PRIMARY KEY (poll_id, device_token)                  -- one vote per device per poll (FR-3.2)
);

-- F2 comments (D29). Anonymous by construction: text and time only, no session, device, IP or nickname column.
CREATE TABLE IF NOT EXISTS comment (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    text       TEXT NOT NULL,
    created_at REAL NOT NULL
);

-- F4 video summary jobs (D34). One row per job. No transcript, file name, path or media column (FR-4.5):
-- only the status, the summary text and timestamps are kept.
CREATE TABLE IF NOT EXISTS summary_job (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    status            TEXT    NOT NULL CHECK (status IN ('queued', 'extracting_audio', 'transcribing',
                                                         'summarising', 'done', 'failed')),
    is_active         INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    progress          REAL    NOT NULL DEFAULT 0 CHECK (progress BETWEEN 0 AND 1),
    summary_language  TEXT,
    detected_language TEXT,
    media_seconds     REAL,
    summary_text      TEXT    CHECK (summary_text IS NULL OR status = 'done'),
    error_message     TEXT    CHECK (error_message IS NULL OR status = 'failed'),
    created_at        REAL    NOT NULL,
    updated_at        REAL    NOT NULL,
    finished_at       REAL
);
-- At most one active job at a time (FR-4.6), enforced by the database as defence in depth.
CREATE UNIQUE INDEX IF NOT EXISTS one_active_summary_job ON summary_job(is_active) WHERE is_active = 1;
