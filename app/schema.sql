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

-- Lecturer-edited lists: kind is 'campus_range' or 'peer_repo'.
CREATE TABLE IF NOT EXISTS setting_item (
    kind  TEXT NOT NULL,
    value TEXT NOT NULL,
    PRIMARY KEY (kind, value)
);
