const { spawn, execSync } = require('child_process');
const path = require('path');
const fs = require('fs');
const AdmZip = require(path.resolve(__dirname, '../backend/node_modules/adm-zip'));

const DB_PORT = process.env.TEST_DB_PORT || 5001;
const AUTH_PORT = process.env.TEST_AUTH_PORT || 4001;
const BACKEND_PORT = process.env.TEST_BACKEND_PORT || 3001;

const DB_URL = `http://localhost:${DB_PORT}`;
const AUTH_URL = `http://localhost:${AUTH_PORT}`;
const BACKEND_URL = `http://localhost:${BACKEND_PORT}`;

const TEST_SECRET = 'test-filewiz-secret-key-32-chars-minimum-entropy';
const INTERNAL_HEADERS = { 'x-internal-service-key': TEST_SECRET };
const ADMIN_HEADERS = { 'x-admin-key': TEST_SECRET };

const TEST_DB_PATH = path.resolve(__dirname, '../database/data/test_e2e_filewiz.sqlite');

let dbProcess = null;
let authProcess = null;
let backendProcess = null;

// ANSI colors for clean test reporting
const colors = {
  reset: '\x1b[0m',
  green: '\x1b[32m',
  red: '\x1b[31m',
  yellow: '\x1b[33m',
  blue: '\x1b[34m',
  cyan: '\x1b[36m',
  bold: '\x1b[1m',
  dim: '\x1b[2m'
};

async function waitForUrl(url, timeoutMs = 20000, intervalMs = 400) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    try {
      const res = await fetch(url, { signal: AbortSignal.timeout(1500) });
      if (res.ok) {
        return true;
      }
    } catch (e) {
      // Service not ready yet
    }
    await new Promise((r) => setTimeout(r, intervalMs));
  }
  throw new Error(`Service at ${url} failed to respond within ${timeoutMs}ms`);
}

async function startServices() {
  console.log(`${colors.cyan}${colors.bold}>>> Starting Isolated Test Services...${colors.reset}`);

  // Clean up any old test database
  if (fs.existsSync(TEST_DB_PATH)) {
    try { fs.unlinkSync(TEST_DB_PATH); } catch (e) {}
  }

  // 1. Start Database Service
  console.log(`  Starting Database Service on port ${DB_PORT}...`);
  dbProcess = spawn(process.execPath, ['src/server.js'], {
    cwd: path.resolve(__dirname, '../database'),
    env: {
      ...process.env,
      PORT: String(DB_PORT),
      SQLITE_DB_PATH: TEST_DB_PATH,
      INTERNAL_SERVICE_KEY: TEST_SECRET
    },
    stdio: 'pipe'
  });

  dbProcess.on('error', (err) => console.error('Database process error:', err));

  // 2. Start Authentication Service
  console.log(`  Starting Authentication Service on port ${AUTH_PORT}...`);
  authProcess = spawn(process.execPath, ['src/server.js'], {
    cwd: path.resolve(__dirname, '../authentication'),
    env: {
      ...process.env,
      PORT: String(AUTH_PORT),
      DATABASE_SERVICE_URL: DB_URL,
      JWT_SECRET: TEST_SECRET,
      SESSION_SECRET: TEST_SECRET,
      INTERNAL_SERVICE_KEY: TEST_SECRET,
      ADMIN_KEY: TEST_SECRET,
      NODE_ENV: 'test'
    },
    stdio: 'pipe'
  });

  authProcess.on('error', (err) => console.error('Auth process error:', err));

  // 3. Start Backend Service
  console.log(`  Starting Backend Service on port ${BACKEND_PORT}...`);
  backendProcess = spawn(process.execPath, ['src/server.js'], {
    cwd: path.resolve(__dirname, '../backend'),
    env: {
      ...process.env,
      PORT: String(BACKEND_PORT),
      JWT_SECRET: TEST_SECRET,
      SESSION_SECRET: TEST_SECRET,
      NODE_ENV: 'test'
    },
    stdio: 'pipe'
  });

  backendProcess.on('error', (err) => console.error('Backend process error:', err));

  // Wait for all three services to pass health checks
  console.log('  Waiting for services to become healthy...');
  await Promise.all([
    waitForUrl(`${DB_URL}/health`),
    waitForUrl(`${AUTH_URL}/health`),
    waitForUrl(`${BACKEND_URL}/health`)
  ]);

  console.log(`${colors.green}  ✓ All 3 microservices are healthy and ready!${colors.reset}\n`);
}

function killProcess(proc) {
  if (!proc || !proc.pid) return;
  try {
    if (process.platform === 'win32') {
      execSync(`taskkill /pid ${proc.pid} /T /F >nul 2>&1`);
    } else {
      proc.kill('SIGTERM');
    }
  } catch (e) {
    // Already terminated
  }
}

async function stopServices() {
  console.log(`\n${colors.cyan}${colors.bold}>>> Tearing Down Test Services...${colors.reset}`);
  killProcess(backendProcess);
  killProcess(authProcess);
  killProcess(dbProcess);

  // Clean up test sqlite database
  if (fs.existsSync(TEST_DB_PATH)) {
    try { fs.unlinkSync(TEST_DB_PATH); } catch (e) {}
  }

  // Clean up any leftover outputs in backend
  const backendOutputs = path.resolve(__dirname, '../backend/temp/outputs');
  if (fs.existsSync(backendOutputs)) {
    const files = fs.readdirSync(backendOutputs);
    for (const f of files) {
      if (f.startsWith('compressed-') || f.startsWith('test_')) {
        try { fs.unlinkSync(path.join(backendOutputs, f)); } catch (e) {}
      }
    }
  }

  console.log(`${colors.green}  ✓ All test services stopped and cleanup finished.${colors.reset}\n`);
}

function getSamplePdf() {
  const candidate = path.resolve(__dirname, '../backend/src/python/scripts/tests/test.pdf');
  if (fs.existsSync(candidate)) {
    return fs.readFileSync(candidate);
  }
  throw new Error(`Sample PDF not found at ${candidate}`);
}

function createSampleZip() {
  const zip = new AdmZip();
  zip.addFile('readme.txt', Buffer.from('Hello FileWiz end-to-end test!'));
  zip.addFile('config.json', Buffer.from(JSON.stringify({ name: 'filewiz-test', active: true })));
  return zip.toBuffer();
}

function createMaliciousZipSlip() {
  const zip = new AdmZip();
  zip.addFile('payload.txt', Buffer.from('evil payload'));
  zip.getEntries()[0].entryName = '../../evil.txt';
  return zip.toBuffer();
}

module.exports = {
  DB_URL,
  AUTH_URL,
  BACKEND_URL,
  INTERNAL_HEADERS,
  ADMIN_HEADERS,
  TEST_SECRET,
  startServices,
  stopServices,
  getSamplePdf,
  createSampleZip,
  createMaliciousZipSlip,
  colors
};
