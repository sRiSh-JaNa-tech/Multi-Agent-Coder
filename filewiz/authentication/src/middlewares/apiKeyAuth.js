const API_KEYS = {
    "your-dev-api-key-123": {
        name: "Developer A",
        permissions: "read"
    },
    "fw_live_sec_key_482910": {
        name: "Production Service Client",
        permissions: "read-write"
    },
    "filewiz-test-key-valid": {
        name: "Test Runner",
        permissions: "admin"
    }
};

const apiKeyAuth = (req, res, next) => {
    const apiKey = req.headers['x-api-key'] || req.headers['X-API-Key'];

    if (!apiKey) {
        return res.status(401).json({ error: 'Unauthorized', message: 'API Key is missing' });
    }

    const keyData = API_KEYS[apiKey];

    if (!keyData) {
        return res.status(401).json({ error: 'Unauthorized', message: 'Invalid API Key' });
    }

    // Attach key data to request for further use
    req.apiKeyData = keyData;
    next();
};

module.exports = apiKeyAuth;
