// Database Service Connector for Authentication Microservice
// Communicates with the dedicated database service in the database/ directory

const DATABASE_SERVICE_URL = process.env.DATABASE_SERVICE_URL || 'http://database-service:5000';

/**
 * Health check with the dedicated Database Service
 */
const checkDatabaseHealth = async () => {
    try {
        const url = process.env.DATABASE_SERVICE_URL || 'http://localhost:5000';
        const res = await fetch(`${url}/health`, { signal: AbortSignal.timeout(3000) });
        if (res.ok) {
            const data = await res.json();
            console.log("[AUTH SERVICE] Connected to dedicated Database Service:", data.service);
            return true;
        }
    } catch (err) {
        console.warn("[AUTH SERVICE] Warning: Database service not reachable at startup:", err.message);
    }
    return false;
};

module.exports = {
    DATABASE_SERVICE_URL,
    checkDatabaseHealth
};
