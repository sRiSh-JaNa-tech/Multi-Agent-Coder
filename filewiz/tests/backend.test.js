const assert = require('node:assert/strict');
const { BACKEND_URL, getSamplePdf, createSampleZip, createMaliciousZipSlip, colors } = require('./test-helper');

async function runBackendTests(authToken) {
  console.log(`\n${colors.blue}${colors.bold}========================================`);
  console.log(`  SUITE 3: Backend Microservice & Security Hardening`);
  console.log(`========================================${colors.reset}`);

  const samplePdfBuffer = getSamplePdf();
  let lastDownloadLink = null;

  // 1. Health check
  {
    process.stdout.write('  1. Health check (GET /health)... ');
    const res = await fetch(`${BACKEND_URL}/health`);
    assert.equal(res.status, 200);
    const data = await res.json();
    assert.equal(data.status, 'ok');
    assert.equal(data.service, 'filewiz-backend');
    console.log(`${colors.green}PASSED${colors.reset}`);
  }

  // 2. Root API check
  {
    process.stdout.write('  2. Root status endpoint (GET /)... ');
    const res = await fetch(`${BACKEND_URL}/`);
    assert.equal(res.status, 200);
    const text = await res.text();
    assert.ok(text.includes('FileWiz Backend API'));
    console.log(`${colors.green}PASSED${colors.reset}`);
  }

  // 3. Security: Auth middleware blocks unauthenticated requests to /compress/pdf (401)
  {
    process.stdout.write('  3. Security: Auth middleware blocks unauthenticated requests to /compress/pdf (401 Unauthorized)... ');
    const res = await fetch(`${BACKEND_URL}/compress/pdf/result`, { method: 'POST' });
    assert.equal(res.status, 401, 'Unauthenticated compress request must be blocked');
    console.log(`${colors.green}PASSED${colors.reset}`);
  }

  // 4. Security: Auth middleware blocks unauthenticated requests to /split/pdf (401)
  {
    process.stdout.write('  4. Security: Auth middleware blocks unauthenticated requests to /split/pdf (401 Unauthorized)... ');
    const res = await fetch(`${BACKEND_URL}/split/pdf/result`, { method: 'POST' });
    assert.equal(res.status, 401, 'Unauthenticated split request must be blocked');
    console.log(`${colors.green}PASSED${colors.reset}`);
  }

  // 5. Security: Auth middleware blocks unauthenticated requests to /peek (401)
  {
    process.stdout.write('  5. Security: Auth middleware blocks unauthenticated requests to /peek (401 Unauthorized)... ');
    const res = await fetch(`${BACKEND_URL}/peek/result`, { method: 'POST' });
    assert.equal(res.status, 401, 'Unauthenticated peek request must be blocked');
    console.log(`${colors.green}PASSED${colors.reset}`);
  }

  // 6. Security: Auth middleware blocks unauthenticated requests to /encrypt (401)
  {
    process.stdout.write('  6. Security: Auth middleware blocks unauthenticated requests to /encrypt (401 Unauthorized)... ');
    const res = await fetch(`${BACKEND_URL}/encrypt/upload`, { method: 'POST' });
    assert.equal(res.status, 401, 'Unauthenticated encrypt request must be blocked');
    console.log(`${colors.green}PASSED${colors.reset}`);
  }

  // 7. Authenticated 7-Zip PDF Compression (Normal profile)
  {
    process.stdout.write('  7. Authenticated 7-Zip PDF Compression (POST /compress/pdf/result with Bearer token)... ');
    const formData = new FormData();
    formData.append('files', new Blob([samplePdfBuffer], { type: 'application/pdf' }), 'test.pdf');
    formData.append('compressionLevel', 'normal');

    const res = await fetch(`${BACKEND_URL}/compress/pdf/result`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${authToken}`
      },
      body: formData
    });

    assert.equal(res.status, 200, `Expected 200 but got ${res.status}`);
    const data = await res.json();
    assert.equal(data.success, true);
    assert.ok(data.stats, 'Response must include stats');
    assert.ok(data.stats.reduction, 'Stats must include reduction percentage');
    assert.ok(data.downloadLink, 'Response must include downloadLink');
    assert.ok(data.downloadLink.endsWith('.7z'), 'Download link must point to a .7z archive');

    lastDownloadLink = data.downloadLink;
    console.log(`${colors.green}PASSED (Reduction: ${data.stats.reduction})${colors.reset}`);
  }

  // 8. Download and verify the generated 7-Zip archive (.7z)
  {
    process.stdout.write('  8. Download & verify 7-Zip signature (377abcaf271c)... ');
    const res = await fetch(`${BACKEND_URL}${lastDownloadLink}`, {
      headers: { 'Authorization': `Bearer ${authToken}` }
    });
    assert.equal(res.status, 200, 'Download endpoint should return 200');

    const arrayBuffer = await res.arrayBuffer();
    const buffer = Buffer.from(arrayBuffer);
    assert.ok(buffer.length > 0, 'Downloaded archive must not be empty');

    const magicHeader = buffer.subarray(0, 6).toString('hex');
    assert.equal(magicHeader, '377abcaf271c', 'File must begin with valid 7-Zip signature');
    console.log(`${colors.green}PASSED (Valid 7z magic signature verified)${colors.reset}`);
  }

  // 9. Security: Block Command Injection payload in split ranges
  {
    process.stdout.write('  9. Security: Block Command Injection payload in page ranges (400 Bad Request)... ');
    const formData = new FormData();
    formData.append('pdf', new Blob([samplePdfBuffer], { type: 'application/pdf' }), 'test.pdf');
    formData.append('splitMode', 'range');
    formData.append('ranges', '1-2" & whoami & "'); // Command Injection attempt

    const res = await fetch(`${BACKEND_URL}/split/pdf/result`, {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${authToken}` },
      body: formData
    });

    assert.equal(res.status, 400, 'Command injection payload must be rejected with 400');
    const data = await res.json();
    assert.ok(data.error.includes('Invalid page range format'));
    console.log(`${colors.green}PASSED (Command injection thwarted)${colors.reset}`);
  }

  // 10. Security: Block Zip Slip directory traversal in archive extraction
  {
    process.stdout.write('  10. Security: Block Zip Slip Directory Traversal in ZIP extraction (400 Bad Request)... ');
    const maliciousZip = createMaliciousZipSlip();
    const formData = new FormData();
    formData.append('archive', new Blob([maliciousZip], { type: 'application/zip' }), 'slip.zip');

    const res = await fetch(`${BACKEND_URL}/peek/result`, {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${authToken}` },
      body: formData
    });

    assert.equal(res.status, 400, 'Malicious Zip Slip must be rejected with 400');
    const data = await res.json();
    assert.ok(data.error.includes('Zip Slip') || data.error.includes('traversal'));
    console.log(`${colors.green}PASSED (Zip Slip prevented)${colors.reset}`);
  }

  // 11. Security: Block Arbitrary File Exfiltration in /split/pdf/download
  {
    process.stdout.write('  11. Security: Block Arbitrary File Exfiltration in ZIP packaging (403 Forbidden)... ');
    const res = await fetch(`${BACKEND_URL}/split/pdf/download`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${authToken}`
      },
      body: JSON.stringify({
        selectedFiles: ['../../../../etc/passwd', 'C:\\Windows\\win.ini']
      })
    });

    assert.equal(res.status, 403, 'Path traversal in archive packaging must return 403 Forbidden');
    console.log(`${colors.green}PASSED (File exfiltration blocked)${colors.reset}`);
  }

  // 12. Security: Block MIME spoofing / fake magic bytes
  {
    process.stdout.write('  12. Security: Block MIME spoofing / fake file pretending to be PDF (400 Bad Request)... ');
    const fakePdf = Buffer.from('THIS IS JUST PLAIN TEXT NOT A REAL PDF DOCUMENT');
    const formData = new FormData();
    formData.append('files', new Blob([fakePdf], { type: 'application/pdf' }), 'fake.pdf');
    formData.append('compressionLevel', 'normal');

    const res = await fetch(`${BACKEND_URL}/compress/pdf/result`, {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${authToken}` },
      body: formData
    });

    assert.equal(res.status, 400, 'Fake PDF magic bytes must be rejected with 400');
    const data = await res.json();
    assert.ok(data.error.includes('signature'));
    console.log(`${colors.green}PASSED (MIME spoofing blocked)${colors.reset}`);
  }

  // 13. Authenticated ZIP Inspection
  {
    process.stdout.write('  13. Authenticated legitimate ZIP inspection (POST /peek/result)... ');
    const validZip = createSampleZip();
    const formData = new FormData();
    formData.append('archive', new Blob([validZip], { type: 'application/zip' }), 'valid.zip');

    const res = await fetch(`${BACKEND_URL}/peek/result`, {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${authToken}` },
      body: formData
    });

    assert.equal(res.status, 200);
    const data = await res.json();
    assert.equal(data.success, true);
    assert.ok(data.workspaceId);
    assert.ok(data.tree);
    console.log(`${colors.green}PASSED (Workspace: ${data.workspaceId})${colors.reset}`);
  }

  console.log(`${colors.green}${colors.bold}>>> Backend Microservice & Security Suite: ALL 13 TESTS PASSED${colors.reset}\n`);
}

module.exports = { runBackendTests };
