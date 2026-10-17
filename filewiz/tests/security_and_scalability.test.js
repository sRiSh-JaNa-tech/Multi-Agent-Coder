const assert = require('assert');
const {
  AUTH_URL,
  BACKEND_URL,
  startServices,
  stopServices,
  colors
} = require('./test-helper');

async function runSecurityAndScalabilityTests() {
  console.log(`\n${colors.cyan}${colors.bold}========================================`);
  console.log(`  SUITE 5: Security Hardening & Async Scalability`);
  console.log(`========================================${colors.reset}`);

  // Test 1: Rate Limiter on Auth Service
  process.stdout.write('  1. Rate Limiter: Enforce sliding-window threshold (HTTP 429)... ');
  {
    const requests = [];
    // Send 15 rapid concurrent requests (limit is 5 in test mode)
    for (let i = 0; i < 15; i++) {
      requests.push(fetch(`${AUTH_URL}/some/endpoint`));
    }
    const responses = await Promise.all(requests);
    const statuses = responses.map(r => r.status);
    const rateLimited = statuses.filter(s => s === 429);
    assert(rateLimited.length > 0, `Expected at least one HTTP 429 response, received: ${statuses.join(', ')}`);
    console.log(`${colors.green}PASSED${colors.reset} (Blocked ${rateLimited.length} requests with HTTP 429)`);
  }

  // Test 2: API Key Authentication Middleware
  process.stdout.write('  2. API Key Auth: Reject missing API key (HTTP 401)... ');
  {
    const res = await fetch(`${AUTH_URL}/protected/resource`);
    assert.strictEqual(res.status, 401, `Expected 401, got ${res.status}`);
    const body = await res.json();
    assert(body.error || body.message, 'Expected error response body');
    console.log(`${colors.green}PASSED${colors.reset}`);
  }

  process.stdout.write('  3. API Key Auth: Reject invalid API key (HTTP 401)... ');
  {
    const res = await fetch(`${AUTH_URL}/protected/resource`, {
      headers: { 'x-api-key': 'malicious-invalid-key-999' }
    });
    assert.strictEqual(res.status, 401, `Expected 401, got ${res.status}`);
    console.log(`${colors.green}PASSED${colors.reset}`);
  }

  process.stdout.write('  4. API Key Auth: Accept valid registered API key (HTTP 200)... ');
  {
    const res = await fetch(`${AUTH_URL}/protected/resource`, {
      headers: { 'x-api-key': 'fw_live_sec_key_482910' }
    });
    assert.strictEqual(res.status, 200, `Expected 200, got ${res.status}`);
    const body = await res.json();
    assert.strictEqual(body.success, true);
    assert.strictEqual(body.apiKeyData.name, 'Production Service Client');
    console.log(`${colors.green}PASSED${colors.reset} (Authorized: ${body.apiKeyData.name})`);
  }

  // Test 5: Refresh Token Rotation
  process.stdout.write('  5. Auth: Refresh Token Rotation (POST /auth/refresh)... ');
  {
    // First, register and login to get initial tokens
    await fetch(`${AUTH_URL}/auth/signup`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: 'Security Tester', age: 25, email: 'sec_tester@example.com', password: 'Password123!' })
    });
    const loginRes = await fetch(`${AUTH_URL}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: 'sec_tester@example.com', password: 'Password123!' })
    });
    const loginData = await loginRes.json();
    const originalToken = loginData.token;

    // Use token to request a refresh
    const refreshRes = await fetch(`${AUTH_URL}/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refreshToken: originalToken })
    });
    assert.strictEqual(refreshRes.status, 200, `Expected 200, got ${refreshRes.status}`);
    const refreshData = await refreshRes.json();
    assert.strictEqual(refreshData.success, true);
    assert(refreshData.token, 'Expected new access token in response');
    assert(refreshData.refreshToken, 'Expected rotated refresh token');
    console.log(`${colors.green}PASSED${colors.reset} (Token rotated successfully)`);
  }

  // Test 6: Asynchronous Job Processing Queue
  process.stdout.write('  6. Async Scalability: Submit job to queue (POST /api/v1/jobs)... ');
  let jobId = null;
  {
    const res = await fetch(`${BACKEND_URL}/api/v1/jobs`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        jobType: 'CONVERT_DOCUMENT',
        jobData: { source: 'sample.pdf', target: 'sample.docx' }
      })
    });
    assert.strictEqual(res.status, 201, `Expected 201, got ${res.status}`);
    const body = await res.json();
    assert(body.jobId !== undefined || body.id !== undefined, 'Expected jobId in response');
    jobId = body.jobId !== undefined ? body.jobId : body.id;
    assert.strictEqual(body.status, 'PENDING');
    console.log(`${colors.green}PASSED${colors.reset} (Job #${jobId} queued with status: PENDING)`);
  }

  process.stdout.write('  7. Async Scalability: Poll job status until COMPLETED... ');
  {
    let attempts = 0;
    let finalStatus = 'PENDING';
    while (attempts < 15) {
      await new Promise(r => setTimeout(r, 120));
      const res = await fetch(`${BACKEND_URL}/api/v1/jobs/${jobId}/status`);
      assert.strictEqual(res.status, 200, `Expected 200 from status endpoint`);
      const body = await res.json();
      finalStatus = body.status;
      if (finalStatus === 'COMPLETED' || finalStatus === 'FAILED') break;
      attempts++;
    }
    assert.strictEqual(finalStatus, 'COMPLETED', `Expected job to complete, but got ${finalStatus}`);
    console.log(`${colors.green}PASSED${colors.reset} (Job transition: PENDING -> COMPLETED in ${attempts * 120}ms)`);
  }

  // Test 8: Kubernetes Liveness and Readiness Probes
  process.stdout.write('  8. Scalability: Backend Liveness & Readiness Probes (GET /health/*)... ');
  {
    const livenessRes = await fetch(`${BACKEND_URL}/health/liveness`);
    assert.strictEqual(livenessRes.status, 200);
    const liveness = await livenessRes.json();
    assert.strictEqual(liveness.status, 'healthy');
    assert.strictEqual(liveness.check, 'liveness');

    const readinessRes = await fetch(`${BACKEND_URL}/health/readiness`);
    assert.strictEqual(readinessRes.status, 200);
    const readiness = await readinessRes.json();
    assert.strictEqual(readiness.status, 'healthy');
    assert.strictEqual(readiness.check, 'readiness');
    assert(readiness.queue.isHealthy, 'Queue health check should be true');

    const deepRes = await fetch(`${BACKEND_URL}/health/deep`);
    assert.strictEqual(deepRes.status, 200);
    const deep = await deepRes.json();
    assert.strictEqual(deep.status, 'healthy');

    console.log(`${colors.green}PASSED${colors.reset} (Liveness, Readiness & Deep Probes verified)`);
  }

  console.log(`${colors.cyan}>>> Security Hardening & Async Scalability Suite: ALL 8 TESTS PASSED${colors.reset}\n`);
}

// Support standalone direct execution
if (require.main === module) {
  (async () => {
    let hasError = false;
    try {
      await startServices();
      await runSecurityAndScalabilityTests();
    } catch (err) {
      hasError = true;
      console.error(`\n${colors.red}${colors.bold}>>> SECURITY & SCALABILITY TESTS FAILED:${colors.reset}`, err);
    } finally {
      await stopServices();
    }
    process.exit(hasError ? 1 : 0);
  })();
}

module.exports = { runSecurityAndScalabilityTests };
