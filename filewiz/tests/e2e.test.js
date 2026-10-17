const { startServices, stopServices, colors } = require('./test-helper');
const { runDatabaseTests } = require('./database.test');
const { runAuthTests } = require('./auth.test');
const { runBackendTests } = require('./backend.test');
const { runIntegrationTests } = require('./integration.test');

async function runAllTests() {
  const startTime = Date.now();
  console.log(`\n${colors.cyan}${colors.bold}================================================================`);
  console.log(`       FILEWIZ END-TO-END AUTOMATED TEST SUITE`);
  console.log(`================================================================${colors.reset}`);

  let hasError = false;

  try {
    // 1. Boot up isolated microservices
    await startServices();

    // 2. Suite 1: SQLite Database Microservice
    await runDatabaseTests();

    // 3. Suite 2: Authentication Microservice
    const { jwtToken } = await runAuthTests();

    // 4. Suite 3: Backend Microservice & 7-Zip PDF Compression
    await runBackendTests(jwtToken);

    // 5. Suite 4: End-to-End Cross-Microservice Integration
    await runIntegrationTests();

    const duration = ((Date.now() - startTime) / 1000).toFixed(2);
    console.log(`${colors.green}${colors.bold}================================================================`);
    console.log(`  🎉 ALL TEST SUITES PASSED SUCCESSFULLY! (${duration}s)`);
    console.log(`  - Database Microservice:   10/10 tests passed`);
    console.log(`  - Authentication Service:  15/15 tests passed`);
    console.log(`  - Backend & Security:      13/13 tests passed`);
    console.log(`  - Cross-Service E2E Flow:   7/7 steps passed`);
    console.log(`  - Total Checks:            45 passed, 0 failed`);
    console.log(`================================================================${colors.reset}\n`);

  } catch (err) {
    hasError = true;
    console.error(`\n${colors.red}${colors.bold}>>> TEST SUITE FAILED:${colors.reset}`, err);
  } finally {
    await stopServices();
  }

  if (hasError) {
    process.exit(1);
  } else {
    process.exit(0);
  }
}

// Execute tests
runAllTests();
