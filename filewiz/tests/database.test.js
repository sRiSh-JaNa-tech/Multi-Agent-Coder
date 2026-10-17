const assert = require('node:assert/strict');
const { DB_URL, INTERNAL_HEADERS, colors } = require('./test-helper');

async function runDatabaseTests() {
  console.log(`\n${colors.blue}${colors.bold}========================================`);
  console.log(`  SUITE 1: SQLite Database Microservice`);
  console.log(`========================================${colors.reset}`);

  let testUserId = null;
  const testEmail = `dbtest_${Date.now()}@filewiz.local`;

  // 1. Health check
  {
    process.stdout.write('  1. Health check (GET /health)... ');
    const res = await fetch(`${DB_URL}/health`);
    assert.equal(res.status, 200, 'Health endpoint should return 200');
    const data = await res.json();
    assert.equal(data.status, 'ok');
    assert.equal(data.engine, 'sqlite');
    assert.equal(data.service, 'filewiz-database');
    console.log(`${colors.green}PASSED${colors.reset}`);
  }

  // 2. Security Test: Reject unauthenticated direct access without internal service key
  {
    process.stdout.write('  2. Security: Reject direct access without internal service key (403 Forbidden)... ');
    const res = await fetch(`${DB_URL}/users`);
    assert.equal(res.status, 403, 'Direct public request to /users must be blocked with 403');
    const data = await res.json();
    assert.ok(data.error.includes('Forbidden'));
    console.log(`${colors.green}PASSED (Blocked unauthorized access)${colors.reset}`);
  }

  // 3. Save user with internal key
  {
    process.stdout.write('  3. Create user record with internal key (POST /users)... ');
    const payload = {
      name: 'Test Database User',
      age: 28,
      email: testEmail,
      password: '$2a$10$hashedpasswordfore2etestingonly'
    };
    const res = await fetch(`${DB_URL}/users`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...INTERNAL_HEADERS
      },
      body: JSON.stringify(payload)
    });
    assert.equal(res.status, 201, 'POST /users should return 201 Created');
    const data = await res.json();
    assert.equal(data.success, true);
    assert.ok(data.user.id, 'User record must have an ID');
    assert.equal(data.user.email, testEmail.toLowerCase());
    assert.equal(data.user.name, payload.name);
    assert.equal(data.user.age, 28);
    testUserId = data.user.id;
    console.log(`${colors.green}PASSED (User ID: ${testUserId})${colors.reset}`);
  }

  // 4. Duplicate email rejection
  {
    process.stdout.write('  4. Reject duplicate email (POST /users)... ');
    const res = await fetch(`${DB_URL}/users`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...INTERNAL_HEADERS
      },
      body: JSON.stringify({
        name: 'Another User',
        email: testEmail,
        password: 'password123'
      })
    });
    assert.equal(res.status, 409, 'Duplicate user should return 409 Conflict');
    const data = await res.json();
    assert.ok(data.error.includes('already exists'));
    console.log(`${colors.green}PASSED${colors.reset}`);
  }

  // 5. Missing fields rejection
  {
    process.stdout.write('  5. Reject missing fields (POST /users)... ');
    const res = await fetch(`${DB_URL}/users`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...INTERNAL_HEADERS
      },
      body: JSON.stringify({ name: 'Incomplete' })
    });
    assert.equal(res.status, 400, 'Missing email/password should return 400');
    console.log(`${colors.green}PASSED${colors.reset}`);
  }

  // 6. Security: Retrieve user by email strips password hash by default
  {
    process.stdout.write('  6. Security: Password hash stripped on normal query (GET /users/email/:email)... ');
    const res = await fetch(`${DB_URL}/users/email/${encodeURIComponent(testEmail)}`, {
      headers: INTERNAL_HEADERS
    });
    assert.equal(res.status, 200, 'Should return 200 OK');
    const data = await res.json();
    assert.equal(data.success, true);
    assert.equal(data.user.email, testEmail.toLowerCase());
    assert.equal(data.user.id, testUserId);
    assert.equal(data.user.password, undefined, 'Password MUST be stripped from response');
    console.log(`${colors.green}PASSED (Password field safely omitted)${colors.reset}`);
  }

  // 7. Retrieve user by email with internal password flag (for auth service verification only)
  {
    process.stdout.write('  7. Retrieve user by email with internal password flag... ');
    const res = await fetch(`${DB_URL}/users/email/${encodeURIComponent(testEmail)}?includePassword=true`, {
      headers: INTERNAL_HEADERS
    });
    assert.equal(res.status, 200);
    const data = await res.json();
    assert.ok(data.user.password, 'Password must be returned when requested by authorized service');
    console.log(`${colors.green}PASSED${colors.reset}`);
  }

  // 8. Retrieve user by ID
  {
    process.stdout.write('  8. Retrieve user by ID (GET /users/id/:id)... ');
    const res = await fetch(`${DB_URL}/users/id/${testUserId}`, {
      headers: INTERNAL_HEADERS
    });
    assert.equal(res.status, 200);
    const data = await res.json();
    assert.equal(data.success, true);
    assert.equal(data.user.id, testUserId);
    assert.equal(data.user.password, undefined);
    console.log(`${colors.green}PASSED${colors.reset}`);
  }

  // 9. List all users (password stripped)
  {
    process.stdout.write('  9. List all users with passwords stripped (GET /users)... ');
    const res = await fetch(`${DB_URL}/users`, {
      headers: INTERNAL_HEADERS
    });
    assert.equal(res.status, 200);
    const data = await res.json();
    assert.equal(data.success, true);
    assert.ok(Array.isArray(data.users));
    assert.ok(data.users.every(u => u.password === undefined), 'All passwords stripped');
    console.log(`${colors.green}PASSED (Count: ${data.users.length})${colors.reset}`);
  }

  // 10. Delete user
  {
    process.stdout.write('  10. Delete user by ID (DELETE /users/id/:id)... ');
    const res = await fetch(`${DB_URL}/users/id/${testUserId}`, {
      method: 'DELETE',
      headers: INTERNAL_HEADERS
    });
    assert.equal(res.status, 200);
    const data = await res.json();
    assert.equal(data.success, true);

    // Verify deletion
    const verifyRes = await fetch(`${DB_URL}/users/id/${testUserId}`, {
      headers: INTERNAL_HEADERS
    });
    assert.equal(verifyRes.status, 404, 'User should return 404 after deletion');
    console.log(`${colors.green}PASSED${colors.reset}`);
  }

  console.log(`${colors.green}${colors.bold}>>> Database Microservice Suite: ALL 10 TESTS PASSED${colors.reset}\n`);
}

module.exports = { runDatabaseTests };
