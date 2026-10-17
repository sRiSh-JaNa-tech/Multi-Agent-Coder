// In-memory store for tracking request counts and timestamps
const requestTimestamps = {};
const WINDOW_SIZE_MS = 60 * 1000; // 1 minute
const getLimit = () => {
    if (process.env.RATE_LIMIT_MAX) return parseInt(process.env.RATE_LIMIT_MAX, 10);
    return process.env.NODE_ENV === 'test' ? 5 : 100;
};

const rateLimiter = (req, res, next) => {
    const ip = req.ip || req.socket.remoteAddress || '127.0.0.1';
    const now = Date.now();
    const limit = getLimit();

    // Initialize IP if not present
    if (!requestTimestamps[ip]) {
        requestTimestamps[ip] = [];
    }

    // Remove timestamps older than the window
    requestTimestamps[ip] = requestTimestamps[ip].filter(
        (timestamp) => timestamp > now - WINDOW_SIZE_MS
    );

    // Set standard rate limit headers
    const remaining = Math.max(0, limit - requestTimestamps[ip].length);
    res.setHeader('X-RateLimit-Limit', limit);
    res.setHeader('X-RateLimit-Remaining', remaining);

    // Check if the number of requests exceeds the limit
    if (requestTimestamps[ip].length >= limit) {
        res.setHeader('Retry-After', '60');
        return res.status(429).json({
            error: "Too Many Requests",
            message: "Rate limit exceeded. Please wait a moment before sending more requests."
        });
    }

    // Add the current timestamp and proceed
    requestTimestamps[ip].push(now);
    next();
};

module.exports = rateLimiter;
