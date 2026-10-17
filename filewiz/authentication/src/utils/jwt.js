const jwt = require('jsonwebtoken');

const KNOWN_INSECURE_SECRETS = [
    "filewiz-super-secret-jwt-key",
    "filewiz-super-secret-production-jwt-key",
    "super-secret-key"
];

function getJwtSecret() {
    const secret = process.env.JWT_SECRET;
    if (process.env.NODE_ENV === 'production') {
        if (!secret || KNOWN_INSECURE_SECRETS.includes(secret) || secret.length < 32) {
            throw new Error(
                "FATAL SECURITY CONFIGURATION: Production boot rejected. " +
                "JWT_SECRET must be explicitly defined with a high-entropy secret (min 32 characters)."
            );
        }
        return secret;
    }
    return secret || "filewiz-dev-jwt-secret-do-not-use-in-prod";
}

const JWT_EXPIRES_IN = process.env.JWT_EXPIRES_IN || "7d";

exports.signToken = (payload) => {
    return jwt.sign(payload, getJwtSecret(), {
        expiresIn: JWT_EXPIRES_IN
    });
};

exports.verifyToken = (token) => {
    return jwt.verify(token, getJwtSecret());
};
