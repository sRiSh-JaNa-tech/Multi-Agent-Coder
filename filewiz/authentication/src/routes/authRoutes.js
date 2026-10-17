const express = require('express');
const router = express.Router();
const User = require('../models/User');
const { signToken, verifyToken } = require('../utils/jwt');
const accountLockout = require('../middlewares/accountLockout');

// Session check endpoint
router.get('/session', (req, res) => {
    // Check JWT cookie first
    const token = req.cookies.auth_token;
    if (token) {
        try {
            const decoded = verifyToken(token);
            return res.json({ loggedIn: true, user: { email: decoded.email, name: decoded.name } });
        } catch (err) {
            // Invalid token - fall through to session check
        }
    }

    if (req.session && req.session.user) {
        return res.json({ loggedIn: true, user: req.session.user });
    }

    return res.json({ loggedIn: false, user: null });
});

// Current user profile endpoint
router.get('/me', (req, res) => {
    const token = req.cookies.auth_token || req.headers.authorization?.replace('Bearer ', '');
    if (!token) {
        return res.status(401).json({ error: "Unauthorized" });
    }
    try {
        const decoded = verifyToken(token);
        return res.json({ success: true, user: decoded });
    } catch (err) {
        return res.status(401).json({ error: "Invalid or expired token" });
    }
});

// Login endpoint
router.post('/login', accountLockout, async (req, res) => {
    try {
        const { email, password } = req.body;
        if (!email || !password) {
            return res.status(400).json({ error: "Email and password are required" });
        }

        const user = await User.login(email, password);
        if (!user) {
            if (req.incrementLoginFailure) req.incrementLoginFailure();
            return res.status(401).json({ error: "Invalid email or password" });
        }

        const tokenPayload = {
            id: user.id || user._id,
            email: user.email,
            name: user.name || user.email.split('@')[0]
        };

        const token = signToken(tokenPayload);

        // Set HTTP-only cookie for secure browser sessions
        res.cookie('auth_token', token, {
            httpOnly: true,
            secure: process.env.NODE_ENV === 'production',
            sameSite: 'lax',
            maxAge: 7 * 24 * 60 * 60 * 1000 // 7 days
        });

        if (req.session) {
            req.session.user = { email: user.email, name: user.name };
        }

        if (req.resetLoginFailures) req.resetLoginFailures();
        return res.json({
            success: true,
            token,
            user: {
                email: user.email,
                name: user.name
            }
        });
    } catch (err) {
        console.error("Login route error:", err);
        return res.status(500).json({ error: "Internal server error during login" });
    }
});

// Signup endpoint
router.post('/signup', async (req, res) => {
    try {
        const { name, age, email, password } = req.body;
        if (!email || !password) {
            return res.status(400).json({ error: "Email and password are required" });
        }

        const existingUser = await User.findByEmail(email);
        if (existingUser) {
            return res.status(400).json({ error: "User already exists with this email" });
        }

        const user = new User(name, age, email, password);
        await user.create();

        return res.json({ success: true, message: "User registered successfully" });
    } catch (err) {
        console.error("Signup route error:", err);
        return res.status(500).json({ error: "Internal server error during registration" });
    }
});

// Logout endpoint
router.all('/logout', (req, res) => {
    res.clearCookie('auth_token');
    if (req.session) {
        req.session.destroy(() => {
            return res.json({ success: true, message: "Logged out successfully" });
        });
    } else {
        return res.json({ success: true, message: "Logged out successfully" });
    }
});

// Token verification endpoint (for internal microservice calls)
router.post('/verify', (req, res) => {
    const token = req.body.token || req.cookies.auth_token || req.headers.authorization?.replace('Bearer ', '');
    if (!token) {
        return res.status(401).json({ valid: false, error: "No token provided" });
    }
    try {
        const decoded = verifyToken(token);
        return res.json({ valid: true, user: decoded });
    } catch (err) {
        return res.status(401).json({ valid: false, error: "Invalid or expired token" });
    }
});

// Refresh token rotation endpoint
router.post('/refresh', (req, res) => {
    const token = req.body.refreshToken || req.cookies.refresh_token || req.body.token;
    if (!token) {
        return res.status(400).json({ error: "Refresh token is required" });
    }
    try {
        const decoded = verifyToken(token);
        const newPayload = { id: decoded.id, email: decoded.email, name: decoded.name };
        const newToken = signToken(newPayload);
        const newRefreshToken = signToken(newPayload);

        res.cookie('auth_token', newToken, {
            httpOnly: true,
            secure: process.env.NODE_ENV === 'production',
            sameSite: 'lax',
            maxAge: 7 * 24 * 60 * 60 * 1000
        });

        return res.json({
            success: true,
            token: newToken,
            refreshToken: newRefreshToken,
            user: newPayload
        });
    } catch (err) {
        return res.status(401).json({ error: "Invalid or expired refresh token" });
    }
});

const apiKeyAuth = require('../middlewares/apiKeyAuth');
const rateLimiter = require('../middlewares/rateLimiter');

// API Key Protected resource
router.get('/protected/resource', apiKeyAuth, (req, res) => {
    res.json({
        success: true,
        message: "Access granted via API Key",
        apiKeyData: req.apiKeyData
    });
});

// Rate-limited resource
router.get('/some/endpoint', rateLimiter, (req, res) => {
    res.json({ success: true, message: "OK" });
});

// ── Administrative / Internal Protected Endpoints ──────────────────
function requireAdmin(req, res, next) {
    const adminKey = process.env.ADMIN_KEY || process.env.INTERNAL_SERVICE_KEY || 'filewiz-internal-db-secret';
    const provided = req.headers['x-admin-key'] || req.headers['x-internal-service-key'];
    if (!provided || provided !== adminKey) {
        return res.status(403).json({ error: "Forbidden: Administrative access required" });
    }
    next();
}

// Retrieve all users from SQLite (Admin only)
router.get('/users', requireAdmin, async (req, res) => {
    try {
        const users = await User.getAll();
        return res.json({ success: true, count: users.length, users });
    } catch (err) {
        console.error("Error retrieving users from SQLite:", err);
        return res.status(500).json({ error: "Failed to retrieve users" });
    }
});

// Retrieve a user by email from SQLite (Admin only)
router.get('/user/:email', requireAdmin, async (req, res) => {
    try {
        const user = await User.findByEmail(req.params.email);
        if (!user) {
            return res.status(404).json({ error: "User not found" });
        }
        return res.json({ success: true, user });
    } catch (err) {
        console.error("Error retrieving user from SQLite:", err);
        return res.status(500).json({ error: "Failed to retrieve user" });
    }
});

// Retrieve a user by ID from SQLite (Admin only)
router.get('/user/id/:id', requireAdmin, async (req, res) => {
    try {
        const user = await User.findById(req.params.id);
        if (!user) {
            return res.status(404).json({ error: "User not found" });
        }
        return res.json({ success: true, user });
    } catch (err) {
        console.error("Error retrieving user from SQLite:", err);
        return res.status(500).json({ error: "Failed to retrieve user" });
    }
});

module.exports = router;
