require('dotenv').config();
const express = require('express');
const cors = require('cors');
const helmet = require('helmet');
const { initDatabase, run, get, all, dbPath } = require('./db');

const app = express();
const PORT = process.env.PORT || 5000;
const INTERNAL_SERVICE_KEY = process.env.INTERNAL_SERVICE_KEY || 'filewiz-internal-db-secret';

app.use(helmet());
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

// Restrict CORS to internal cluster or localhost callers
const allowedOrigins = [
    process.env.FRONTEND_ORIGIN || 'http://localhost:5173',
    'http://localhost:4000',
    'http://localhost:3000'
];

app.use(cors({
    origin: function (origin, callback) {
        if (!origin || allowedOrigins.includes(origin)) {
            return callback(null, true);
        }
        return callback(new Error('Blocked by CORS policy for Database Service'));
    },
    credentials: true
}));

// Logger
app.use((req, res, next) => {
    console.log(`[DATABASE SERVICE] ${req.method} ${req.url}`);
    next();
});

// Health check (public within cluster for probes)
app.get('/health', (req, res) => {
    res.json({
        status: 'ok',
        service: 'filewiz-database',
        engine: 'sqlite',
        dbPath: dbPath,
        timestamp: new Date().toISOString()
    });
});

// 🛡️ Service-to-Service Internal Authentication Middleware
function verifyInternalAccess(req, res, next) {
    const providedKey = req.headers['x-internal-service-key'] || req.headers['authorization']?.replace('Bearer ', '');
    if (!providedKey || providedKey !== INTERNAL_SERVICE_KEY) {
        return res.status(403).json({
            error: "Forbidden: Direct public access to database service is restricted to authorized microservices."
        });
    }
    next();
}

// Protect all /users endpoints with internal service authentication
app.use('/users', verifyInternalAccess);

// ── User CRUD Operations in SQLite ─────────────────────────────────────

// 1. Save user data into SQLite
app.post('/users', (req, res) => {
    try {
        const { name, age, email, password, createdAt } = req.body;
        if (!name || !email || !password) {
            return res.status(400).json({ error: "Name, email, and password are required" });
        }

        const normalizedEmail = email.toLowerCase().trim();
        const existing = get("SELECT id FROM users WHERE email = ?;", [normalizedEmail]);
        if (existing) {
            return res.status(409).json({ error: "User with this email already exists" });
        }

        const recordDate = createdAt || new Date().toISOString();
        const parsedAge = age ? parseInt(age, 10) : null;

        const result = run(
            `INSERT INTO users (name, age, email, password, created_at) VALUES (?, ?, ?, ?, ?);`,
            [name, parsedAge, normalizedEmail, password, recordDate]
        );

        return res.status(201).json({
            success: true,
            user: {
                id: result.lastInsertRowid,
                name,
                age: parsedAge,
                email: normalizedEmail,
                createdAt: recordDate
            }
        });
    } catch (err) {
        console.error("[DATABASE SERVICE] Error saving user to SQLite:", err);
        return res.status(500).json({ error: "Failed to save user data in SQLite", details: err.message });
    }
});

// 2. Retrieve all users from SQLite (Password hash stripped)
app.get('/users', (req, res) => {
    try {
        const rows = all(`SELECT id, name, age, email, created_at FROM users ORDER BY id DESC;`);
        return res.json({ success: true, count: rows.length, users: rows });
    } catch (err) {
        console.error("[DATABASE SERVICE] Error retrieving users from SQLite:", err);
        return res.status(500).json({ error: "Failed to retrieve users from SQLite", details: err.message });
    }
});

// 3. Retrieve user by email from SQLite
app.get('/users/email/:email', (req, res) => {
    try {
        const normalizedEmail = req.params.email.toLowerCase().trim();
        const includePassword = req.query.includePassword === 'true';

        // Password hash only provided for internal authentication validation
        const fields = includePassword
            ? "id, name, age, email, password, created_at"
            : "id, name, age, email, created_at";

        const user = get(`SELECT ${fields} FROM users WHERE email = ?;`, [normalizedEmail]);
        if (!user) {
            return res.status(404).json({ error: "User not found" });
        }

        return res.json({ success: true, user });
    } catch (err) {
        console.error("[DATABASE SERVICE] Error retrieving user by email:", err);
        return res.status(500).json({ error: "Failed to retrieve user from SQLite", details: err.message });
    }
});

// 4. Retrieve user by ID from SQLite (Password hash stripped)
app.get('/users/id/:id', (req, res) => {
    try {
        const id = parseInt(req.params.id, 10);
        const user = get(`SELECT id, name, age, email, created_at FROM users WHERE id = ?;`, [id]);
        if (!user) {
            return res.status(404).json({ error: "User not found" });
        }

        return res.json({ success: true, user });
    } catch (err) {
        console.error("[DATABASE SERVICE] Error retrieving user by id:", err);
        return res.status(500).json({ error: "Failed to retrieve user from SQLite", details: err.message });
    }
});

// 5. Delete user by ID (Internal service only)
app.delete('/users/id/:id', (req, res) => {
    try {
        const id = parseInt(req.params.id, 10);
        run(`DELETE FROM users WHERE id = ?;`, [id]);
        return res.json({ success: true, message: `User ${id} deleted` });
    } catch (err) {
        return res.status(500).json({ error: "Failed to delete user" });
    }
});

// Start database service
initDatabase()
    .then(() => {
        app.listen(PORT, () => {
            console.log(`[DATABASE SERVICE] SQLite database service running on port ${PORT}`);
            console.log(`[DATABASE SERVICE] Database file: ${dbPath}`);
        });
    })
    .catch((err) => {
        console.error("[DATABASE SERVICE] Fatal: failed to start database service:", err);
        process.exit(1);
    });

module.exports = app;
