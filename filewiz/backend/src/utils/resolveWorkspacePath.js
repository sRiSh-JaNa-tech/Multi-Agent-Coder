const path = require('path');
const rootDir = require('./pathUtils');

function resolveWorkspacePath(ws, relativePath = '') {
  if (!ws) {
    throw new Error('Workspace missing');
  }

  // Normalize path
  const cleanPath = relativePath.replace(/^\/+/, '');

  if (cleanPath.includes('..')) {
    throw new Error('Invalid path');
  }

  return path.join(
    rootDir,
    'temp',
    'workspaces',
    ws,
    'extracted',
    cleanPath
  );
}

module.exports = resolveWorkspacePath;