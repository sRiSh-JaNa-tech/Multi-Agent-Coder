const initSqlJs = require('sql.js');
const fs = require('fs');
const path = require('path');

let _db = null;
let _SQL = null;

const dbPath = process.env.SQLITE_DB_PATH || path.join(__dirname, '../data/filewiz.sqlite');

/**
 * Persists SQLite in-memory state to physical disk
 */
const saveDatabase = () => {
    if (!_db) return;
    try {
        const dir = path.dirname(dbPath);
        if (!fs.existsSync(dir)) {
            fs.mkdirSync(dir, { recursive: true });
        }
        const data = _db.export();
        fs.writeFileSync(dbPath, Buffer.from(data));
    } catch (err) {
        console.error("[DATABASE SERVICE] Failed to save SQLite database:", err.message);
    }
};

/**
 * Initializes SQLite database and applies schema
 */
const initDatabase = async () => {
    try {
        if (!_SQL) {
            _SQL = await initSqlJs();
        }

        const dir = path.dirname(dbPath);
        if (!fs.existsSync(dir)) {
            fs.mkdirSync(dir, { recursive: true });
        }

        if (fs.existsSync(dbPath)) {
            const fileBuffer = fs.readFileSync(dbPath);
            _db = new _SQL.Database(fileBuffer);
            console.log("[DATABASE SERVICE] Loaded existing SQLite database from:", dbPath);
        } else {
            _db = new _SQL.Database();
            console.log("[DATABASE SERVICE] Created new SQLite database at:", dbPath);
        }

        // Apply schema
        const schemaPath = path.join(__dirname, '../schema.sql');
        let schemaSql = `
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                age INTEGER,
                email TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
        `;
        if (fs.existsSync(schemaPath)) {
            schemaSql = fs.readFileSync(schemaPath, 'utf-8');
        }

        _db.run(schemaSql);
        saveDatabase();
        console.log("[DATABASE SERVICE] SQLite schema verified and ready.");
        return _db;
    } catch (err) {
        console.error("[DATABASE SERVICE] Initialization failed:", err);
        throw err;
    }
};

const getDb = () => {
    if (!_db) {
        throw new Error("[DATABASE SERVICE] Database not initialized. Call initDatabase() first.");
    }
    return _db;
};

const run = (sql, params = []) => {
    const db = getDb();
    db.run(sql, params);
    saveDatabase();

    try {
        const res = db.exec("SELECT max(id) AS id FROM users;");
        const lastId = res && res[0] && res[0].values && res[0].values[0] ? res[0].values[0][0] : null;
        return { lastInsertRowid: lastId };
    } catch {
        return { lastInsertRowid: null };
    }
};

const get = (sql, params = []) => {
    const db = getDb();
    const stmt = db.prepare(sql);
    try {
        if (params && params.length > 0) {
            stmt.bind(params);
        }
        if (stmt.step()) {
            return stmt.getAsObject();
        }
        return null;
    } finally {
        stmt.free();
    }
};

const all = (sql, params = []) => {
    const db = getDb();
    const stmt = db.prepare(sql);
    const results = [];
    try {
        if (params && params.length > 0) {
            stmt.bind(params);
        }
        while (stmt.step()) {
            results.push(stmt.getAsObject());
        }
        return results;
    } finally {
        stmt.free();
    }
};

module.exports = {
    initDatabase,
    getDb,
    run,
    get,
    all,
    saveDatabase,
    dbPath
};
