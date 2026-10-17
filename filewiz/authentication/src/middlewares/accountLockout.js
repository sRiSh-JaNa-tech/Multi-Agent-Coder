const MAX_FAILED_ATTEMPTS = 5;
const LOCKOUT_WINDOW_MS = 15 * 60 * 1000; // 15 minutes

const failedAttempts = {}; // In-memory store: { identifier: { count: number, timestamp: number } }

const accountLockout = (req, res, next) => {
    const identifier = req.body?.email || req.ip || req.socket?.remoteAddress || '127.0.0.1';
    req.loginAttemptIdentifier = identifier;

    // Clean up old expired entries
    const now = Date.now();
    for (const id in failedAttempts) {
        if (now - failedAttempts[id].timestamp > LOCKOUT_WINDOW_MS) {
            delete failedAttempts[id];
        }
    }

    // Attach helper methods to req
    req.incrementLoginFailure = () => {
        const id = req.loginAttemptIdentifier;
        if (!id) return;
        failedAttempts[id] = failedAttempts[id] || { count: 0, timestamp: now };
        failedAttempts[id].count++;
        failedAttempts[id].timestamp = Date.now();
    };

    req.resetLoginFailures = () => {
        const id = req.loginAttemptIdentifier;
        if (!id) return;
        if (failedAttempts[id]) {
            delete failedAttempts[id];
        }
    };

    // Check if account/IP is locked
    if (failedAttempts[identifier] && failedAttempts[identifier].count >= MAX_FAILED_ATTEMPTS) {
        if (now - failedAttempts[identifier].timestamp < LOCKOUT_WINDOW_MS) {
            res.setHeader('Retry-After', '900');
            return res.status(429).json({
                error: "Account Locked",
                message: "Account locked. Too many failed login attempts. Please try again in 15 minutes."
            });
        } else {
            delete failedAttempts[identifier];
        }
    }

    next();
};

module.exports = accountLockout;
