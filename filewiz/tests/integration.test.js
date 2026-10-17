const assert = require('node:assert/strict');
const { DB_URL, AUTH_URL, BACKEND_URL, INTERNAL_HEADERS, getSamplePdf, createSampleZip, colors } = require('./test-helper');

async function runIntegrationTests() {
  console.log(`\n${colors.blue}${colors.bold}================================================================`);
  console.log(`  SUITE 4: Full End-to-End Cross-Microservice Integration Flow`);
  console.log(`================================================================${colors.reset}`);

  const user = {
    name: 'E2E Full Journey User',
    age: 26,
    email: `e2e_journey_${Date.now()}@filewiz.local`,
    password: 'FileWizSecure2026!'
  };

  let token = null;
  let userId = null;

  // Step 1: User signs up through Auth service
  {
    process.stdout.write('  Step 1: User registers via Auth service (Auth -> SQLite)... ');
    const res = await fetch(`${AUTH_URL}/auth/signup`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(user)
    });
    assert.equal(res.status, 200);
    const data = await res.json();
    assert.equal(data.success, true);
    console.log(`${colors.green}PASSED${colors.reset}`);
  }

  // Step 2: Verify user was saved directly in SQLite Database service (using internal microservice key)
  {
    process.stdout.write('  Step 2: Verify user record directly in SQLite Database service... ');
    const res = await fetch(`${DB_URL}/users/email/${encodeURIComponent(user.email)}`, {
      headers: INTERNAL_HEADERS
    });
    assert.equal(res.status, 200);
    const data = await res.json();
    assert.equal(data.success, true);
    assert.equal(data.user.email, user.email.toLowerCase());
    assert.equal(data.user.name, user.name);
    assert.equal(data.user.password, undefined, 'Password hash is strictly omitted');
    userId = data.user.id;
    console.log(`${colors.green}PASSED (Stored in SQLite with ID: ${userId})${colors.reset}`);
  }

  // Step 3: User logs in through Auth service to get JWT token
  {
    process.stdout.write('  Step 3: User logs in via Auth service to acquire JWT session token... ');
    const res = await fetch(`${AUTH_URL}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: user.email, password: user.password })
    });
    assert.equal(res.status, 200);
    const data = await res.json();
    assert.equal(data.success, true);
    assert.ok(data.token);
    token = data.token;
    console.log(`${colors.green}PASSED (JWT acquired)${colors.reset}`);
  }

  // Step 4: Access Backend protected endpoint using the Auth token
  {
    process.stdout.write('  Step 4: User accesses Backend service using Auth token (Auth -> Backend)... ');
    const zipBuffer = createSampleZip();
    const formData = new FormData();
    formData.append('archive', new Blob([zipBuffer], { type: 'application/zip' }), 'journey_test.zip');

    const res = await fetch(`${BACKEND_URL}/peek/result`, {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${token}` },
      body: formData
    });
    assert.equal(res.status, 200);
    const data = await res.json();
    assert.equal(data.success, true);
    console.log(`${colors.green}PASSED (Authorized with cross-service JWT)${colors.reset}`);
  }

  // Step 5: User executes authenticated 7-Zip PDF compression in Backend
  let downloadLink = null;
  {
    process.stdout.write('  Step 5: User runs authenticated 7-Zip PDF compression in Backend service... ');
    const pdfBuffer = getSamplePdf();
    const formData = new FormData();
    formData.append('files', new Blob([pdfBuffer], { type: 'application/pdf' }), 'journey_doc.pdf');
    formData.append('compressionLevel', 'extreme');

    const res = await fetch(`${BACKEND_URL}/compress/pdf/result`, {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${token}` },
      body: formData
    });
    assert.equal(res.status, 200);
    const data = await res.json();
    assert.equal(data.success, true);
    assert.ok(data.stats);
    assert.ok(data.downloadLink);
    downloadLink = data.downloadLink;
    console.log(`${colors.green}PASSED (7-Zip compressed, size: ${data.stats.before} -> ${data.stats.after})${colors.reset}`);
  }

  // Step 6: User downloads the compressed 7-Zip file from Backend
  {
    process.stdout.write('  Step 6: User downloads .7z archive and verifies integrity... ');
    const res = await fetch(`${BACKEND_URL}${downloadLink}`, {
      headers: { 'Authorization': `Bearer ${token}` }
    });
    assert.equal(res.status, 200);
    const arrayBuffer = await res.arrayBuffer();
    const buffer = Buffer.from(arrayBuffer);
    assert.ok(buffer.length > 0);
    // 7-Zip signature check
    assert.equal(buffer.subarray(0, 6).toString('hex'), '377abcaf271c');
    console.log(`${colors.green}PASSED (Valid 7-Zip archive downloaded, size: ${buffer.length} bytes)${colors.reset}`);
  }

  // Step 7: Clean up user from Database service using internal key
  {
    process.stdout.write('  Step 7: Clean up test user from SQLite Database service... ');
    const res = await fetch(`${DB_URL}/users/id/${userId}`, {
      method: 'DELETE',
      headers: INTERNAL_HEADERS
    });
    assert.equal(res.status, 200);
    console.log(`${colors.green}PASSED${colors.reset}`);
  }

  console.log(`${colors.green}${colors.bold}>>> Cross-Microservice Integration Suite: ALL 7 STEPS PASSED${colors.reset}\n`);
}

module.exports = { runIntegrationTests };
