-- FileWiz SQLite Database Schema
-- Table: users

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    age INTEGER,
    email TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    created_at TEXT NOT NULL
);

-- Index for high-performance user lookups by email
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
