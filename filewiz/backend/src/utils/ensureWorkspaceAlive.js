async function ensureWorkspaceAlive(ws) {
  const metaPath = path.join(
    rootDir,
    'temp',
    'workspaces',
    ws,
    'meta.json'
  );

  const meta = JSON.parse(await fs.readFile(metaPath, 'utf8'));

  if (new Date(meta.expiresAt) < new Date()) {
    throw new Error('Workspace expired');
  }
}
