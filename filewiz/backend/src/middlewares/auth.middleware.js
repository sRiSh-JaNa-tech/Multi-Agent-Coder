const { verifyToken } = require('../utils/jwt');

module.exports = function isAuthenticated(req, res, next) {
    // 1. Check Bearer token in Authorization header
    const authHeader = req.headers.authorization;
    let token = authHeader && authHeader.startsWith('Bearer ') ? authHeader.split(' ')[1] : null;

    // 2. Check auth_token cookie
    if (!token && req.cookies && req.cookies.auth_token) {
        token = req.cookies.auth_token;
    }

    if (token) {
        try {
            const decoded = verifyToken(token);
            req.user = decoded;
            return next();
        } catch (err) {
            // Invalid or expired token
        }
    }

    // 3. Fallback to session
    if (req.session && req.session.user) {
        req.user = req.session.user;
        return next();
    }

    return res.status(401).json({ error: 'Unauthorized. Please log in to continue.' });
};