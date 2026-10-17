const crypto = require('crypto');
const { FREE_USAGE_LIMIT } = require('../utils/constants');

// 🔒 Server-side state store for anonymous rate limiting
// Map<string, { count: number, resetAt: number }>
const serverUsageStore = new Map();

// Cleanup expired server-side usage records periodically
setInterval(() => {
    const now = Date.now();
    for (const [key, record] of serverUsageStore.entries()) {
        if (now > record.resetAt) {
            serverUsageStore.delete(key);
        }
    }
}, 60 * 60 * 1000);

const HMAC_SECRET = process.env.JWT_SECRET || 'filewiz-usage-hmac-secret';

module.exports = function usageLimit(req, res, next) {
    // Authenticated users bypass anonymous quota constraints
    if (req.user) {
        return next();
    }

    const clientIp = (req.headers['x-forwarded-for']?.split(',')[0].trim()) || req.ip || req.socket.remoteAddress || 'unknown';
    const now = Date.now();
    const WINDOW_MS = 24 * 60 * 60 * 1000; // 24 hours

    let record = serverUsageStore.get(clientIp);
    if (!record || now > record.resetAt) {
        record = { count: 0, resetAt: now + WINDOW_MS };
        serverUsageStore.set(clientIp, record);
    }

    if (record.count >= FREE_USAGE_LIMIT) {
        return res.status(403).json({
            error: 'Free tier usage limit reached. Please log in or sign up to continue.',
            redirect: '/auth/signup'
        });
    }

    record.count += 1;

    // Issue cryptographically signed tamper-proof cookie verification
    const signaturePayload = `${clientIp}:${record.count}:${record.resetAt}`;
    const hmac = crypto.createHmac('sha256', HMAC_SECRET).update(signaturePayload).digest('hex');

    res.cookie('usageProof', `${signaturePayload}.${hmac}`, {
        httpOnly: true,
        secure: process.env.NODE_ENV === 'production',
        sameSite: 'lax',
        maxAge: WINDOW_MS
    });

    next();
};