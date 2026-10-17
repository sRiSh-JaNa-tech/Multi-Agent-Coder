const express = require('express');
const router = express.Router();
const path = require('path');
const fs = require('fs/promises');
const fsSync = require('fs');
const AdmZip = require('adm-zip');
const crypto = require('crypto');
const archiver = require('archiver');

const rootDir = require('../utils/pathUtils');
const upload = require(path.join(rootDir, 'config', 'multer'));
const logger = require('../services/logger');
const buildTree = require('../services/buildTree');
const resolveWorkspacePath = require('../utils/resolveWorkspacePath');
const { validateUploadedFileSignature } = require('../utils/fileSignature');

const EDITABLE_EXTENSIONS = [
  '.js', '.json', '.txt', '.md',
  '.html', '.css', '.ts', '.csv'
];

// 🔒 Anti-Zip-Bomb & Anti-Zip-Slip Limits
const MAX_ARCHIVE_FILES = 2000;
const MAX_TOTAL_UNCOMPRESSED_BYTES = 100 * 1024 * 1024; // 100 MB
const MAX_INDIVIDUAL_FILE_BYTES = 50 * 1024 * 1024;     // 50 MB
const MAX_DECOMPRESSION_RATIO = 50;                     // ratio: uncompressed / compressed

/**
 * Safely extracts a ZIP archive preventing Zip Slip (path traversal)
 * and Zip Bomb (resource exhaustion / disk denial of service).
 */
async function safeExtractZip(zip, extractDir, compressedSize) {
  const resolvedBase = path.resolve(extractDir);
  const entries = zip.getEntries();

  if (entries.length > MAX_ARCHIVE_FILES) {
    throw new Error(`Zip bomb detected: file count (${entries.length}) exceeds safety limit (${MAX_ARCHIVE_FILES})`);
  }

  let totalUncompressedBytes = 0;

  // First pass: validate all entries BEFORE extracting any data
  for (const entry of entries) {
    const rawName = entry.entryName;

    // Disallow null bytes or dangerous characters
    if (rawName.includes('\0')) {
      throw new Error("Malicious entry detected: null byte in path");
    }

    const resolvedTarget = path.resolve(resolvedBase, rawName);

    // Zip Slip check: resolved path MUST be strictly inside resolvedBase
    if (!resolvedTarget.startsWith(resolvedBase + path.sep) && resolvedTarget !== resolvedBase) {
      throw new Error(`Zip Slip path traversal attempt blocked: ${rawName}`);
    }

    if (!entry.isDirectory) {
      const size = entry.header.size;
      if (size > MAX_INDIVIDUAL_FILE_BYTES) {
        throw new Error(`Entry size (${size} bytes) exceeds individual limit of ${MAX_INDIVIDUAL_FILE_BYTES} bytes`);
      }
      totalUncompressedBytes += size;

      if (totalUncompressedBytes > MAX_TOTAL_UNCOMPRESSED_BYTES) {
        throw new Error(`Zip bomb detected: total uncompressed size exceeds ${MAX_TOTAL_UNCOMPRESSED_BYTES} bytes`);
      }

      if (compressedSize > 0 && (totalUncompressedBytes / compressedSize) > MAX_DECOMPRESSION_RATIO) {
        throw new Error(`Zip bomb detected: compression ratio exceeds threshold (${MAX_DECOMPRESSION_RATIO})`);
      }
    }
  }

  // Second pass: safe write
  for (const entry of entries) {
    const resolvedTarget = path.resolve(resolvedBase, entry.entryName);

    if (entry.isDirectory) {
      await fs.mkdir(resolvedTarget, { recursive: true });
    } else {
      await fs.mkdir(path.dirname(resolvedTarget), { recursive: true });
      const data = entry.getData();
      await fs.writeFile(resolvedTarget, data);
    }
  }
}

router.post(
  '/result',
  upload.single('archive'),
  validateUploadedFileSignature('zip', 'archive'),
  async (req, res) => {
    let uploadedFilePath = null;
    try {
      if (!req.file) {
        return res.status(400).json({ error: 'No file uploaded' });
      }

      uploadedFilePath = req.file.path;

      await logger.log(
        `User uploaded archive: ${req.file.originalname}`,
        'INFO',
        'peek-service'
      );

      const workspaceId = `ws_${Date.now()}_${crypto.randomInt(100000, 999999)}`;
      const workspacePath = path.resolve(rootDir, 'temp', 'workspaces', workspaceId);
      const extractPath = path.resolve(workspacePath, 'extracted');

      await fs.mkdir(extractPath, { recursive: true });

      const zip = new AdmZip(uploadedFilePath);

      // 🛡️ Execute Safe Zip Extraction with Zip Slip & Zip Bomb defenses
      await safeExtractZip(zip, extractPath, req.file.size);

      const tree = await buildTree(extractPath);

      // Metadata
      const WORKSPACE_TTL_MINUTES = 30;
      const meta = {
        workspaceId,
        originalZip: path.basename(req.file.originalname),
        createdAt: new Date().toISOString(),
        expiresAt: new Date(
          Date.now() + WORKSPACE_TTL_MINUTES * 60 * 1000
        ).toISOString()
      };

      await fs.writeFile(
        path.join(workspacePath, 'meta.json'),
        JSON.stringify(meta, null, 2)
      );

      return res.json({
        success: true,
        workspaceId,
        tree
      });
    } catch (err) {
      console.error('Error processing peek result:', err);
      return res.status(400).json({ error: err.message || 'Failed to process archive' });
    } finally {
      // Cleanup uploaded zip immediately after extraction
      if (uploadedFilePath && fsSync.existsSync(uploadedFilePath)) {
        try { await fs.rm(uploadedFilePath, { force: true }); } catch (cleanupErr) {
          console.error("Failed to delete uploaded zip:", cleanupErr);
        }
      }
    }
  }
);

router.get('/file', async (req, res) => {
  const { ws, path: relativePath } = req.query;

  if (!ws || !relativePath) {
    return res.status(400).json({ error: 'Missing parameters' });
  }

  if (!/^[a-zA-Z0-9_-]+$/.test(ws)) {
    return res.status(400).json({ error: 'Invalid workspace identifier' });
  }

  // 🔒 Block path traversal
  if (relativePath.includes('..') || relativePath.includes('\0')) {
    return res.status(400).json({ error: 'Invalid path' });
  }

  const baseExtract = path.resolve(rootDir, 'temp', 'workspaces', ws, 'extracted');
  const filePath = path.resolve(baseExtract, relativePath);

  if (!filePath.startsWith(baseExtract + path.sep)) {
    return res.status(403).json({ error: 'Forbidden: Path traversal blocked' });
  }

  // 🔒 Ensure file exists
  try {
    const stat = await fs.stat(filePath);
    if (!stat.isFile()) {
      return res.status(400).json({ error: 'Not a file' });
    }
  } catch {
    return res.status(404).json({ error: 'File not found' });
  }

  const ext = path.extname(filePath).toLowerCase();

  // 🔒 Enforce permissions
  if (!EDITABLE_EXTENSIONS.includes(ext)) {
    return res.status(403).json({ error: 'File is read-only' });
  }

  try {
    const content = await fs.readFile(filePath, 'utf8');
    res.json({ content });
  } catch (err) {
    await logger.log(
      `File read failed: ${filePath}`,
      'ERROR',
      'peek-service'
    );
    res.status(500).json({ error: 'Failed to read file' });
  }
});

router.get('/tree', async (req, res) => {
  const { ws } = req.query;

  if (!ws || !/^[a-zA-Z0-9_-]+$/.test(ws)) {
    return res.status(400).json({ error: 'Invalid workspace identifier' });
  }

  try {
    const extractPath = resolveWorkspacePath(ws);
    const tree = await buildTree(extractPath);
    res.json(tree);
  } catch (err) {
    res.status(400).json({ error: err.message });
  }
});

router.post('/file/save', async (req, res) => {
  const { ws, path: relativePath, content } = req.body;

  if (!ws || !relativePath) {
    return res.status(400).json({ error: 'Missing parameters' });
  }

  if (!/^[a-zA-Z0-9_-]+$/.test(ws)) {
    return res.status(400).json({ error: 'Invalid workspace identifier' });
  }

  // 🔒 Block path traversal
  if (relativePath.includes('..') || relativePath.includes('\0')) {
    return res.status(400).json({ error: 'Invalid path' });
  }

  const baseExtract = path.resolve(rootDir, 'temp', 'workspaces', ws, 'extracted');
  const filePath = path.resolve(baseExtract, relativePath);

  if (!filePath.startsWith(baseExtract + path.sep)) {
    return res.status(403).json({ error: 'Forbidden: Path traversal blocked' });
  }

  const ext = path.extname(filePath).toLowerCase();

  // 🔒 Permission check
  if (!EDITABLE_EXTENSIONS.includes(ext)) {
    return res.status(403).json({ error: 'File is read-only' });
  }

  try {
    await fs.writeFile(filePath, content, 'utf8');

    await logger.log(
      `File saved: ${filePath}`,
      'INFO',
      'peek-service'
    );

    res.json({ success: true });
  } catch (err) {
    await logger.log(
      `File save failed: ${err.message}`,
      'ERROR',
      'peek-service'
    );
    res.status(500).json({ error: 'Failed to save file' });
  }
});

router.get('/download', async (req, res) => {
  const { ws } = req.query;

  if (!ws || !/^[a-zA-Z0-9_-]+$/.test(ws)) {
    return res.status(400).send('Missing or invalid workspace id');
  }

  const workspacePath = path.resolve(rootDir, 'temp', 'workspaces', ws);
  const extractPath = path.resolve(workspacePath, 'extracted');
  const metaPath = path.resolve(workspacePath, 'meta.json');

  // 🔒 Ensure workspace exists
  try {
    await fs.access(extractPath);
  } catch {
    return res.status(404).send('Workspace not found');
  }

  let zipName = 'updated.zip';
  try {
    const meta = JSON.parse(await fs.readFile(metaPath, 'utf8'));
    zipName = path.basename(meta.originalZip) || zipName;
  } catch { }

  res.setHeader(
    'Content-Disposition',
    `attachment; filename="${zipName}"`
  );
  res.setHeader('Content-Type', 'application/zip');

  const archive = archiver('zip', { zlib: { level: 9 } });

  archive.on('error', async (err) => {
    await logger.log(
      `ZIP archive error: ${err.message}`,
      'ERROR',
      'peek-service'
    );
    res.status(500).end();
  });

  archive.pipe(res);
  archive.directory(extractPath, false);
  await archive.finalize();
});

router.post('/file/create', async (req, res) => {
  const { ws, path: relativePath } = req.body;

  try {
    const filePath = resolveWorkspacePath(ws, relativePath);
    await fs.writeFile(filePath, '', { flag: 'wx' });

    await logger.log(
      `File created: ${filePath}`,
      'INFO',
      'peek-service'
    );

    res.json({ success: true });
  } catch (err) {
    res.status(400).json({ error: err.message });
  }
});

router.post('/folder/create', async (req, res) => {
  const { ws, path: relativePath } = req.body;

  try {
    const folderPath = resolveWorkspacePath(ws, relativePath);
    await fs.mkdir(folderPath, { recursive: false });

    await logger.log(
      `Folder created: ${folderPath}`,
      'INFO',
      'peek-service'
    );

    res.json({ success: true });
  } catch (err) {
    res.status(400).json({ error: err.message });
  }
});

router.post('/rename', async (req, res) => {
  const { ws, oldPath, newPath } = req.body;

  try {
    const oldAbs = resolveWorkspacePath(ws, oldPath);
    const newAbs = resolveWorkspacePath(ws, newPath);

    await fs.rename(oldAbs, newAbs);

    await logger.log(
      `Renamed: ${oldAbs} → ${newAbs}`,
      'INFO',
      'peek-service'
    );

    res.json({ success: true });
  } catch (err) {
    res.status(400).json({ error: err.message });
  }
});

router.post('/delete', async (req, res) => {
  const { ws, path: relativePath } = req.body;

  try {
    const targetPath = resolveWorkspacePath(ws, relativePath);
    await fs.rm(targetPath, { recursive: true, force: true });

    await logger.log(
      `Deleted: ${targetPath}`,
      'INFO',
      'peek-service'
    );

    res.json({ success: true });
  } catch (err) {
    res.status(400).json({ error: err.message });
  }
});

module.exports = router;
