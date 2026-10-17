const express = require("express");
const path = require('path');
const fs = require('fs');

const rootDir = require("../utils/pathUtils");
const uploadPPT = require('../config/pptUpload');
const { getFileSizeInBytes, formatBytes } = require('../utils/fileSize');
const { runPython } = require('../utils/pythonRunner');
const { validateUploadedFileSignature } = require('../utils/fileSignature');

const router = express.Router();

const ALLOWED_COMPRESSION_LEVELS = ['low', 'normal', 'extreme', 'high'];

router.post(
  '/result',
  uploadPPT.single('ppt'),
  validateUploadedFileSignature('pptx', 'ppt'),
  async (req, res) => {
    let inputPath = null;
    try {
      if (!req.file) {
        return res.status(400).json({ error: 'Please select a file.' });
      }

      inputPath = req.file.path;
      const rawLevel = req.body.compressionLevel || 'normal';
      const safeLevel = ALLOWED_COMPRESSION_LEVELS.includes(String(rawLevel).toLowerCase())
        ? String(rawLevel).toLowerCase()
        : 'normal';

      const removeMediaFlag = (req.body.removeMedia === 'on' || req.body.removeMedia === true || req.body.removeMedia === 'true')
        ? 'True'
        : 'False';

      // 📏 SIZE BEFORE
      const originalSizeBytes = getFileSizeInBytes(inputPath);

      const outputFileName = `compressed-${Date.now()}.pptx`;
      const outDir = path.resolve(rootDir, 'temp', 'outputs');
      if (!fs.existsSync(outDir)) {
        fs.mkdirSync(outDir, { recursive: true });
      }
      const outputPath = path.join(outDir, outputFileName);

      const pythonScript = path.join(
        rootDir, 'python', 'scripts', 'pptxCompress.py'
      );

      // Safe execution using execFile (zero shell command injection)
      await runPython(pythonScript, [inputPath, outputPath, safeLevel, removeMediaFlag]);

      if (!fs.existsSync(outputPath)) {
        throw new Error("Compressed PPT output was not created");
      }

      // 📏 SIZE AFTER
      const compressedSizeBytes = getFileSizeInBytes(outputPath);

      const stats = {
        before: formatBytes(originalSizeBytes),
        after: formatBytes(compressedSizeBytes),
        reduction: (
          ((originalSizeBytes - compressedSizeBytes) / originalSizeBytes) *
          100
        ).toFixed(2) + '%'
      };

      console.log('PPT Compression stats:', stats);

      return res.json({
        success: true,
        stats,
        downloadLink: `/compress/ppt/download-file/${outputFileName}`
      });

    } catch (err) {
      console.error("PPT Compression Error:", err);
      return res.status(500).json({ error: 'PPT compression failed. Please try again.' });
    } finally {
      if (inputPath && fs.existsSync(inputPath)) {
        try { fs.unlinkSync(inputPath); } catch (e) { console.error("Input clean failed", e); }
      }
    }
  }
);

router.get('/download-file/:fileName', (req, res) => {
  const fileName = req.params.fileName;

  // Strict filename validation to prevent directory traversal
  if (!fileName || !/^compressed-\d+\.pptx$/.test(fileName)) {
    return res.status(400).send('Invalid file name');
  }

  const outDir = path.resolve(rootDir, 'temp', 'outputs');
  const filePath = path.resolve(outDir, fileName);

  if (!filePath.startsWith(outDir + path.sep)) {
    return res.status(403).send('Forbidden');
  }

  if (fs.existsSync(filePath)) {
    res.download(filePath, fileName, (err) => {
      if (err) {
        console.error("Download Error:", err);
      }
    });
  } else {
    res.status(404).send('File not found or expired.');
  }
});

module.exports = router;