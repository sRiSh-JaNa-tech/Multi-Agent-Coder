const fs = require('fs/promises');
const path = require('path');
const rootDir = require('../utils/pathUtils');
const logger = require('./logger');

const WORKSPACES_DIR = path.join(rootDir, 'temp', 'workspaces');

async function cleanupWorkspaces() {
  try {
    const entries = await fs.readdir(WORKSPACES_DIR);

    for (const ws of entries) {
      const metaPath = path.join(
        WORKSPACES_DIR,
        ws,
        'meta.json'
      );

      try {
        const meta = JSON.parse(
          await fs.readFile(metaPath, 'utf8')
        );

        if (new Date(meta.expiresAt) < new Date()) {
          await fs.rm(
            path.join(WORKSPACES_DIR, ws),
            { recursive: true, force: true }
          );

          await logger.log(
            `Workspace expired & deleted: ${ws}`,
            'INFO',
            'cleanup-service'
          );

          console.log(`Cleanup Succeeded for workspace: ${ws}`);
        }
      } catch (err) {
        // Missing or corrupt meta → remove defensively
        await fs.rm(
          path.join(WORKSPACES_DIR, ws),
          { recursive: true, force: true }
        );
      }
    }
    // Existing workspace cleanup logic...
  } catch (err) {
    await logger.log(
      `Workspace cleanup failed: ${err.message}`,
      'ERROR',
      'cleanup-service'
    );
  }

  // --- CLEANUP TEMP UPLOADS & OUTPUTS & SPLITS ---
  const FOLDS_TO_CLEAN = [
    path.join(rootDir, 'temp', 'uploads'),
    path.join(rootDir, 'temp', 'outputs'),
    path.join(rootDir, 'temp', 'splits')
  ];

  for (const folder of FOLDS_TO_CLEAN) {
    try {
      // Ensure folder exists
      try { await fs.access(folder); } catch { continue; }

      const files = await fs.readdir(folder);
      const NOW = Date.now();
      const ONE_HOUR = 60 * 60 * 1000;

      for (const file of files) {
        const filePath = path.join(folder, file);
        try {
          const stats = await fs.stat(filePath);
          if (NOW - stats.mtimeMs > ONE_HOUR) {
            await fs.rm(filePath, { recursive: true, force: true });
            console.log(`Cleaned up old file/folder: ${filePath}`);
          }
        } catch (e) {
          // Ignore errors for individual files
        }
      }

    } catch (err) {
      console.error(`Error cleaning directory ${folder}:`, err);
    }
  }
}

module.exports = cleanupWorkspaces;
