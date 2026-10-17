require('dotenv').config();
const express = require('express');
const cors = require('cors');
const helmet = require('helmet');
const rateLimit = require('express-rate-limit');
const cookieParser = require('cookie-parser');
const session = require('express-session');
const { checkDatabaseHealth, DATABASE_SERVICE_URL } = require('./utils/database');
const authRoutes = require('./routes/authRoutes');

const app = express();
const PORT = process.env.PORT || 4000;

// 🛡️ Apply HTTP Security Headers
app.use(helmet());

// Middleware
app.use(express.json());
app.use(express.urlencoded({ extended: true }));
app.use(cookieParser());

// 🔒 Restrict Permissive CORS
const allowedOrigins = [
    process.env.FRONTEND_ORIGIN || 'http://localhost:5173',
    'http://localhost:80',
    'http://localhost:3000'
];

app.use(cors({
    origin: function (origin, callback) {
        if (!origin || allowedOrigins.includes(origin)) {
            return callback(null, true);
        }
        return callback(new Error('Blocked by CORS policy for FileWiz Authentication'));
    },
    credentials: true
}));

// 🛡️ Authentication Rate Limiting to prevent brute-force and credential stuffing
const authLimiter = rateLimit({
    windowMs: 15 * 60 * 1000, // 15 minutes
    max: process.env.NODE_ENV === 'test' ? 1000 : 100, // Strict limit in production, relaxed in tests
    standardHeaders: true,
    legacyHeaders: false,
    message: { error: 'Too many authentication attempts. Please try again after 15 minutes.' }
});

app.use('/auth/login', authLimiter);
app.use('/auth/signup', authLimiter);

// Enforce Session Secret Security
const sessionSecret = process.env.SESSION_SECRET || (process.env.NODE_ENV === 'production' ? null : 'filewiz-auth-dev-session-secret');
if (process.env.NODE_ENV === 'production' && (!sessionSecret || sessionSecret === 'filewiz-auth-secret-key' || sessionSecret === 'filewiz-production-session-key')) {
    throw new Error('FATAL SECURITY CONFIGURATION: SESSION_SECRET must be set to a secure string in production.');
}

app.use(
    session({
        name: "filewiz-auth-session",
        secret: sessionSecret || "filewiz-auth-dev-session-secret",
        resave: false,
        saveUninitialized: false,
        cookie: {
            httpOnly: true,
            secure: process.env.NODE_ENV === 'production',
            sameSite: 'lax',
            maxAge: 7 * 24 * 60 * 60 * 1000 // 7 days
        }
    })
);

// Request Logger
app.use((req, res, next) => {
    console.log(`[AUTH SERVICE] ${req.method} ${req.url}`);
    next();
});

// Health check endpoints
app.get('/health', (req, res) => {
    res.json({
        status: 'ok',
        service: 'filewiz-auth',
        databaseServiceUrl: DATABASE_SERVICE_URL,
        timestamp: new Date().toISOString()
    });
});

app.get('/health/liveness', (req, res) => {
    res.json({ status: 'healthy', check: 'liveness', uptime: process.uptime() });
});

app.get('/health/readiness', (req, res) => {
    res.json({ status: 'healthy', check: 'readiness', databaseServiceUrl: DATABASE_SERVICE_URL });
});

app.get('/health/deep', (req, res) => {
    res.json({
        status: 'healthy',
        service: 'filewiz-auth',
        uptime: process.uptime(),
        databaseServiceUrl: DATABASE_SERVICE_URL
    });
});

// Mount auth routes both at root and at /auth
app.use('/auth', authRoutes);
app.use('/', authRoutes);

// Start server
app.listen(PORT, async () => {
    console.log(`FileWiz Authentication Service is running on port ${PORT}`);
    await checkDatabaseHealth();
});

module.exports = app;
