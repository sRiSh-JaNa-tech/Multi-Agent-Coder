const express = require("express");
const path = require("path");
const fs = require('fs/promises');
const fsSync = require('fs');

const rootDir = require('../utils/pathUtils');
const uploadPDF = require('../config/pdfConfig');
const { runPython } = require('../utils/pythonRunner');
const { validateUploadedFileSignature } = require('../utils/fileSignature');

const router = express.Router();

// Strict regex for page ranges (e.g., "1-3,5,7-9")
const RANGE_REGEX = /^\d+(?:-\d+)?(?:,\d+(?:-\d+)?)*$/;

router.post(
  '/result',
  uploadPDF.single('pdf'),
  validateUploadedFileSignature('pdf', 'pdf'),
  async (req, res) => {
    let inputPath = null;
    try {
      // 1. Validation
      if (!req.file) {
        return res.status(400).json({ error: 'No PDF uploaded' });
      }

      inputPath = req.file.path;
      const splitMode = String(req.body.splitMode || '').toLowerCase().trim();
      const ranges = req.body.ranges ? String(req.body.ranges).trim() : '';
      const parts = req.body.parts;

      let splitParam = '';

      if (splitMode === 'range') {
        if (!ranges || !RANGE_REGEX.test(ranges)) {
          return res.status(400).json({
            error: 'Invalid page range format. Expected format: 1-3,5,7-9 (digits, hyphens, and commas only).'
          });
        }
        splitParam = ranges;
      } else if (splitMode === 'count') {
        const parsedParts = parseInt(parts, 10);
        if (!Number.isInteger(parsedParts) || parsedParts <= 0 || parsedParts > 1000) {
          return res.status(400).json({
            error: 'Invalid parts count. Must be a positive integer between 1 and 1000.'
          });
        }
        splitParam = String(parsedParts);
      } else {
        return res.status(400).json({ error: 'Invalid splitMode. Must be "range" or "count".' });
      }

      const jobId = `job_${Date.now()}_${Math.floor(Math.random() * 1e6)}`;
      const outputDir = path.resolve(rootDir, 'temp', 'splits', jobId);
      await fs.mkdir(outputDir, { recursive: true });

      const pythonScript = path.join(
        rootDir,
        'python',
        'scripts',
        'pdf_split_gs.py'
      );

      // Safe execution using execFile (zero shell command injection)
      await runPython(pythonScript, [inputPath, outputDir, splitMode, splitParam]);

      // Read split files
      const files = await fs.readdir(outputDir);
      const splitFiles = files
        .filter(f => f.endsWith('.pdf'))
        .map((file) => ({
          name: file,
          jobId,
          previewUrl: `/split/pdf/preview/${jobId}/${encodeURIComponent(file)}`
        }));

      return res.json({
        success: true,
        jobId,
        splitFiles
      });

    } catch (err) {
      console.error("Split PDF Error:", err);
      return res.status(500).json({ error: 'Failed to split PDF. Please check your inputs.' });
    } finally {
      // Cleanup original upload immediately
      if (inputPath && fsSync.existsSync(inputPath)) {
        try { await fs.unlink(inputPath); } catch (e) {}
      }
    }
  }
);

// Preview individual split PDF (authenticated controller endpoint replacing static /temp)
router.get('/preview/:jobId/:fileName', (req, res) => {
  const { jobId, fileName } = req.params;

  if (!jobId || !/^[a-zA-Z0-9_-]+$/.test(jobId)) {
    return res.status(400).send("Invalid jobId");
  }

  const safeFileName = path.basename(fileName);
  if (!safeFileName.endsWith('.pdf')) {
    return res.status(400).send("Invalid file type");
  }

  const baseDir = path.resolve(rootDir, 'temp', 'splits', jobId);
  const targetPath = path.resolve(baseDir, safeFileName);

  if (!targetPath.startsWith(baseDir + path.sep) || !fsSync.existsSync(targetPath)) {
    return res.status(404).send("File not found or expired");
  }

  res.setHeader('Content-Type', 'application/pdf');
  res.sendFile(targetPath);
});

// POST /download (Download selected files as ZIP with strict path confinement)
router.post('/download', async (req, res) => {
  try {
    const { jobId, selectedFiles } = req.body;

    if (!selectedFiles || (Array.isArray(selectedFiles) && selectedFiles.length === 0)) {
      return res.status(400).send("No files selected");
    }

    const filesToProcess = Array.isArray(selectedFiles) ? selectedFiles : [selectedFiles];

    // Determine target directory: either based on jobId or extracted from the files
    let baseSplitsDir = path.resolve(rootDir, 'temp', 'splits');

    let allowedDir = baseSplitsDir;
    if (jobId) {
      if (!/^[a-zA-Z0-9_-]+$/.test(jobId)) {
        return res.status(400).send("Invalid jobId format");
      }
      allowedDir = path.resolve(baseSplitsDir, jobId);
    }

    const verifiedFiles = [];

    for (const item of filesToProcess) {
      const itemStr = String(item).trim();

      // Disallow directory traversal sequences
      if (itemStr.includes('..') || itemStr.includes('\0')) {
        return res.status(403).send("Unauthorized path traversal detected");
      }

      // If full path was provided, ensure it resides inside baseSplitsDir
      let targetPath;
      if (path.isAbsolute(itemStr)) {
        targetPath = path.resolve(itemStr);
      } else if (jobId) {
        targetPath = path.resolve(allowedDir, path.basename(itemStr));
      } else {
        targetPath = path.resolve(baseSplitsDir, itemStr);
      }

      // Path containment check: target MUST be strictly within allowedDir
      if (!targetPath.startsWith(allowedDir + path.sep) && targetPath !== allowedDir) {
        return res.status(403).send("Forbidden: Cannot package files outside user split workspace");
      }

      if (!fsSync.existsSync(targetPath)) {
        return res.status(404).send(`Split file not found or expired: ${path.basename(targetPath)}`);
      }

      verifiedFiles.push({
        path: targetPath,
        name: path.basename(targetPath)
      });
    }

    const archive = require('archiver')('zip', {
      zlib: { level: 9 }
    });

    res.attachment('split_files.zip');
    archive.pipe(res);

    for (const f of verifiedFiles) {
      archive.file(f.path, { name: f.name });
    }

    await archive.finalize();

  } catch (err) {
    console.error("Download Error:", err);
    res.status(500).send("Error creating zip archive");
  }
});

module.exports = router;