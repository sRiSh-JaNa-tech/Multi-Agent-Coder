const assert = require('node:assert/strict');
const { AUTH_URL, ADMIN_HEADERS, colors } = require('./test-helper');

async function runAuthTests() {
  console.log(`\n${colors.blue}${colors.bold}========================================`);
  console.log(`  SUITE 2: Authentication Microservice`);
  console.log(`========================================${colors.reset}`);

  const testEmail = `authtest_${Date.now()}@filewiz.local`;
  const testPassword = 'SecurePassword!987';
  let jwtToken = null;
  let authCookie = null;

  // 1. Health check
  {
    process.stdout.write('  1. Health check (GET /health)... ');
    const res = await fetch(`${AUTH_URL}/health`);
    assert.equal(res.status, 200);
    const data = await res.json();
    assert.equal(data.status, 'ok');
    assert.equal(data.service, 'filewiz-auth');
    assert.ok(data.databaseServiceUrl);
    console.log(`${colors.green}PASSED${colors.reset}`);
  }

  // 2. Signup
  {
    process.stdout.write('  2. Register new user (POST /auth/signup)... ');
    const res = await fetch(`${AUTH_URL}/auth/signup`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: 'FileWiz Auth User',
        age: 30,
        email: testEmail,
        password: testPassword
      })
    });
    assert.equal(res.status, 200, 'Signup should succeed with 200');
    const data = await res.json();
    assert.equal(data.success, true);
    console.log(`${colors.green}PASSED${colors.reset}`);
  }

  // 3. Duplicate signup rejection
  {
    process.stdout.write('  3. Reject duplicate signup (POST /auth/signup)... ');
    const res = await fetch(`${AUTH_URL}/auth/signup`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: 'Another User',
        email: testEmail,
        password: testPassword
      })
    });
    assert.equal(res.status, 400, 'Duplicate signup should return 400');
    const data = await res.json();
    assert.ok(data.error.includes('already exists'));
    console.log(`${colors.green}PASSED${colors.reset}`);
  }

  // 4. Missing fields rejection
  {
    process.stdout.write('  4. Reject missing credentials on signup... ');
    const res = await fetch(`${AUTH_URL}/auth/signup`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: testEmail })
    });
    assert.equal(res.status, 400);
    console.log(`${colors.green}PASSED${colors.reset}`);
  }

  // 5. Successful login
  {
    process.stdout.write('  5. Login with valid password (POST /auth/login)... ');
    const res = await fetch(`${AUTH_URL}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        email: testEmail,
        password: testPassword
      })
    });
    assert.equal(res.status, 200);
    const data = await res.json();
    assert.equal(data.success, true);
    assert.ok(data.token, 'Response must include JWT token');
    assert.equal(data.user.email, testEmail.toLowerCase());
    jwtToken = data.token;

    // Extract cookie
    const setCookieHeader = res.headers.get('set-cookie');
    assert.ok(setCookieHeader, 'Response should set auth cookie');
    authCookie = setCookieHeader.split(';')[0];
    assert.ok(authCookie.startsWith('auth_token='), 'Cookie name must be auth_token');
    console.log(`${colors.green}PASSED (JWT Generated)${colors.reset}`);
  }

  // 6. Login with wrong password
  {
    process.stdout.write('  6. Reject login with wrong password... ');
    const res = await fetch(`${AUTH_URL}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        email: testEmail,
        password: 'wrong_password_123'
      })
    });
    assert.equal(res.status, 401, 'Invalid password should return 401');
    const data = await res.json();
    assert.ok(data.error.includes('Invalid'));
    console.log(`${colors.green}PASSED${colors.reset}`);
  }

  // 7. Login with non-existent user
  {
    process.stdout.write('  7. Reject login with non-existent email... ');
    const res = await fetch(`${AUTH_URL}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        email: 'doesnotexist_random@filewiz.local',
        password: 'password123'
      })
    });
    assert.equal(res.status, 401);
    console.log(`${colors.green}PASSED${colors.reset}`);
  }

  // 8. Session check with cookie
  {
    process.stdout.write('  8. Verify active session with cookie (GET /auth/session)... ');
    const res = await fetch(`${AUTH_URL}/auth/session`, {
      headers: { 'Cookie': authCookie }
    });
    assert.equal(res.status, 200);
    const data = await res.json();
    assert.equal(data.loggedIn, true);
    assert.equal(data.user.email, testEmail.toLowerCase());
    console.log(`${colors.green}PASSED${colors.reset}`);
  }

  // 9. Session check without cookie
  {
    process.stdout.write('  9. Session check without cookie returns loggedIn: false... ');
    const res = await fetch(`${AUTH_URL}/auth/session`);
    assert.equal(res.status, 200);
    const data = await res.json();
    assert.equal(data.loggedIn, false);
    assert.equal(data.user, null);
    console.log(`${colors.green}PASSED${colors.reset}`);
  }

  // 10. Profile check (GET /auth/me) with Bearer token
  {
    process.stdout.write('  10. Get current user profile (GET /auth/me with Bearer token)... ');
    const res = await fetch(`${AUTH_URL}/auth/me`, {
      headers: { 'Authorization': `Bearer ${jwtToken}` }
    });
    assert.equal(res.status, 200);
    const data = await res.json();
    assert.equal(data.success, true);
    assert.equal(data.user.email, testEmail.toLowerCase());
    console.log(`${colors.green}PASSED${colors.reset}`);
  }

  // 11. Profile check without token
  {
    process.stdout.write('  11. Reject GET /auth/me without token (401 Unauthorized)... ');
    const res = await fetch(`${AUTH_URL}/auth/me`);
    assert.equal(res.status, 401);
    console.log(`${colors.green}PASSED${colors.reset}`);
  }

  // 12. Token verification endpoint (POST /auth/verify)
  {
    process.stdout.write('  12. Verify token endpoint for microservices (POST /auth/verify)... ');
    const res = await fetch(`${AUTH_URL}/auth/verify`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token: jwtToken })
    });
    assert.equal(res.status, 200);
    const data = await res.json();
    assert.equal(data.valid, true);
    assert.equal(data.user.email, testEmail.toLowerCase());
    console.log(`${colors.green}PASSED${colors.reset}`);
  }

  // 13. Security: Block unauthenticated access to /auth/users (403 Forbidden)
  {
    process.stdout.write('  13. Security: Block unauthenticated access to /auth/users (403 Forbidden)... ');
    const res = await fetch(`${AUTH_URL}/auth/users`);
    assert.equal(res.status, 403, 'Must reject unauthenticated access to /auth/users');
    console.log(`${colors.green}PASSED (Public data dumping blocked)${colors.reset}`);
  }

  // 14. Retrieve users with admin authorization
  {
    process.stdout.write('  14. Retrieve users with admin header (GET /auth/users)... ');
    const res = await fetch(`${AUTH_URL}/auth/users`, {
      headers: ADMIN_HEADERS
    });
    assert.equal(res.status, 200);
    const data = await res.json();
    assert.equal(data.success, true);
    assert.ok(Array.isArray(data.users));
    console.log(`${colors.green}PASSED${colors.reset}`);
  }

  // 15. Logout
  {
    process.stdout.write('  15. Logout user (POST /auth/logout)... ');
    const res = await fetch(`${AUTH_URL}/auth/logout`, { method: 'POST' });
    assert.equal(res.status, 200);
    const data = await res.json();
    assert.equal(data.success, true);
    const setCookie = res.headers.get('set-cookie');
    assert.ok(setCookie.includes('auth_token=;'), 'Logout must clear auth_token cookie');
    console.log(`${colors.green}PASSED${colors.reset}`);
  }

  console.log(`${colors.green}${colors.bold}>>> Authentication Microservice Suite: ALL 15 TESTS PASSED${colors.reset}\n`);

  return { jwtToken, testEmail };
}

module.exports = { runAuthTests };
