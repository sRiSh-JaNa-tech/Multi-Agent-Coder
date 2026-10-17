# FileWiz Database Service (SQLite)

This directory contains the database schema, SQLite initialization, and configuration for FileWiz.

## Architecture
FileWiz uses **SQLite 3** for saving and retrieving user data.
- **Embedded & Serverless**: Zero network overhead, zero external database daemon required.
- **Persistent Binary Storage**: Stored as a binary SQLite file at `filewiz.sqlite` (or `/data/filewiz.sqlite` in Kubernetes).
- **Cross-Platform**: Uses WebAssembly SQLite (`sql.js`), enabling identical execution across Windows, Linux, and macOS without requiring native C++ build tools.

## Schema (`schema.sql`)
```sql
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    age INTEGER,
    email TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
```

## Operations

### 1. Save User Data
```sql
INSERT INTO users (name, age, email, password, created_at) 
VALUES ('John Doe', 28, 'john@example.com', '$2a$10$hashed_password...', '2026-10-15T08:00:00.000Z');
```

### 2. Retrieve User by Email
```sql
SELECT id, name, age, email, created_at FROM users WHERE email = 'john@example.com';
```

### 3. Retrieve User by ID
```sql
SELECT id, name, age, email, created_at FROM users WHERE id = 1;
```

### 4. Retrieve All Users
```sql
SELECT id, name, age, email, created_at FROM users ORDER BY id DESC;
```
