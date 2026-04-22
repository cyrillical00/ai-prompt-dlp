PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;

CREATE TABLE IF NOT EXISTS submissions (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp         TEXT NOT NULL,
    risk_tier         TEXT NOT NULL,
    matched_patterns  TEXT NOT NULL,
    redacted_preview  TEXT,
    original_length   INTEGER,
    encoding_detected TEXT,
    passed_to_llm     INTEGER DEFAULT 0,
    llm_response_id   TEXT,
    reason_blocked    TEXT
);

CREATE TABLE IF NOT EXISTS pattern_hits (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    submission_id INTEGER NOT NULL REFERENCES submissions(id),
    category      TEXT NOT NULL,
    pattern_name  TEXT NOT NULL,
    tier          TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_submissions_timestamp ON submissions(timestamp);
CREATE INDEX IF NOT EXISTS idx_submissions_risk_tier ON submissions(risk_tier);
CREATE INDEX IF NOT EXISTS idx_pattern_hits_submission_id ON pattern_hits(submission_id);
CREATE INDEX IF NOT EXISTS idx_pattern_hits_category ON pattern_hits(category);
