
const request = require('supertest');
const express = require('express');

// Mock Express app and routes
const app = express();
app.use(express.json());

// Mock job cancellation
let jobs = {};
app.delete('/api/v1/jobs/:jobId', (req, res) => {
    const { jobId } = req.params;
    if (jobs[jobId]) {
        delete jobs[jobId];
        res.status(200).send({ message: 'Job cancelled' });
    } else {
        res.status(404).send({ message: 'Job not found' });
    }
});

// Mock account lockout
let failedLogins = {};
const MAX_FAILED_LOGINS = 5;
const LOCKOUT_DURATION = 60 * 1000; // 1 minute

app.post('/api/v1/login', (req, res) => {
    const { username, password } = req.body;

    if (failedLogins[username] && Date.now() - failedLogins[username].timestamp < LOCKOUT_DURATION) {
        if (failedLogins[username].count >= MAX_FAILED_LOGINS) {
            return res.status(429).send({ message: 'Account locked. Too many failed login attempts.' });
        }
    } else {
        failedLogins[username] = { count: 0, timestamp: Date.now() };
    }

    // Dummy authentication - always fail for testing lockout
    if (password !== 'correct_password') {
        failedLogins[username].count++;
        failedLogins[username].timestamp = Date.now();
        res.status(401).send({ message: 'Authentication failed' });
    } else {
        // Successful login - reset failed attempts
        delete failedLogins[username];
        res.status(200).send({ message: 'Login successful' });
    }
});

// Middleware to add Correlation ID
app.use((req, res, next) => {
    const correlationId = require('crypto').randomBytes(16).toString('hex');
    req.headers['x-correlation-id'] = correlationId;
    res.setHeader('X-Correlation-ID', correlationId);
    next();
});

describe('Security and Scalability Tests', () => {

    beforeAll(() => {
        // Initialize some dummy jobs for testing cancellation
        jobs = {
            'job123': { status: 'running' },
            'job456': { status: 'pending' }
        };
    });

    // Test 1: Correlation ID Header
    test('should return X-Correlation-ID header for all requests', async () => {
        const response = await request(app).get('/'); // Use a simple GET request
        expect(response.status).toBe(200); // Assuming a root endpoint exists and returns 200
        expect(response.header['x-correlation-id']).toBeDefined();
        expect(response.header['x-correlation-id']).toHaveLength(32); // 16 bytes * 2 hex chars/byte
    });

    // Test 2: Job Cancellation
    test('should successfully cancel a job', async () => {
        const jobIdToCancel = 'job123';
        const response = await request(app)
            .delete(`/api/v1/jobs/${jobIdToCancel}`);

        expect(response.status).toBe(200);
        expect(response.body).toHaveProperty('message', 'Job cancelled');
        expect(jobs[jobIdToCancel]).toBeUndefined();
    });

    test('should return 404 if job to cancel is not found', async () => {
        const nonExistentJobId = 'job999';
        const response = await request(app)
            .delete(`/api/v1/jobs/${nonExistentJobId}`);

        expect(response.status).toBe(404);
        expect(response.body).toHaveProperty('message', 'Job not found');
    });

    // Test 3: Account Lockout
    test('should trigger account lockout after 5 consecutive failed logins', async () => {
        const username = 'testuser';
        const password = 'wrong_password';

        // 5 failed logins
        for (let i = 0; i < MAX_FAILED_LOGINS; i++) {
            const response = await request(app)
                .post('/api/v1/login')
                .send({ username, password });
            expect(response.status).toBe(401);
            expect(response.body).toHaveProperty('message', 'Authentication failed');
        }

        // 6th attempt should result in 429 Too Many Requests
        const lockoutResponse = await request(app)
            .post('/api/v1/login')
            .send({ username, password });

        expect(lockoutResponse.status).toBe(429);
        expect(lockoutResponse.body).toHaveProperty('message', 'Account locked. Too many failed login attempts.');
    });

    test('should allow login after lockout duration', async () => {
        const username = 'testuser_late';
        const password = 'wrong_password';
        const correctPassword = 'correct_password';

        // Simulate failed logins to trigger lockout
        for (let i = 0; i < MAX_FAILED_LOGINS; i++) {
            await request(app)
                .post('/api/v1/login')
                .send({ username, password });
        }

        // Advance time to be past the lockout duration
        // This is tricky in tests. We'll mock the Date.now() or simply adjust the lockout logic for testability
        // For simplicity here, we will assume the test environment allows time manipulation or we adjust the constants
        // In a real scenario, you might mock Date.now() or use a library like 'jest-mock-extended' or Sinon.js
        // For this example, we'll manually adjust the failedLogins timestamp to simulate time passing
        // This is a simplification and might need a more robust approach in a real testing framework.

        // Directly manipulating the state for demonstration purposes:
        // Assuming failedLogins[username].timestamp was set ~LOCKOUT_DURATION ago
        // We'll reset it to ensure it's older than LOCKOUT_DURATION
        failedLogins[username] = { count: MAX_FAILED_LOGINS, timestamp: Date.now() - LOCKOUT_DURATION - 1000 };

        // Now, a successful login should be possible
        const successResponse = await request(app)
            .post('/api/v1/login')
            .send({ username, password: correctPassword });

        expect(successResponse.status).toBe(200);
        expect(successResponse.body).toHaveProperty('message', 'Login successful');
    });
});
