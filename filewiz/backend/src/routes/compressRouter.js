const express = require('express');
const path = require('path');
const fs = require('fs');

const rootDir = require("../utils/pathUtils");
const upload = require('../config/pdfConfig');
const compressPdf = require('../services/compress');
const { getFileSizeInBytes, formatBytes } = require('../utils/fileSize');
const { globalLimiter } = require('../utils/concurrencyLimiter');
const { validateUploadedFileSignature } = require('../utils/fileSignature');

const router = express.Router();

const ALLOWED_COMPRESSION_LEVELS = ['low', 'normal', 'extreme', 'high'];

router.post(
  '/result',
  upload.single('files'),
  validateUploadedFileSignature('pdf'),
  async (req, res) => {
    let inputPath = null;
    try {
      if (!req.file) {
        return res.status(400).json({ error: 'Please select a file.' });
      }

      inputPath = req.file.path;
      const rawLevel = req.body.compressionLevel || 'normal';
      if (!ALLOWED_COMPRESSION_LEVELS.includes(String(rawLevel).toLowerCase())) {
        return res.status(400).json({
          error: `Invalid compressionLevel. Allowed values: ${ALLOWED_COMPRESSION_LEVELS.join(', ')}`
        });
      }
      const compressionLevel = String(rawLevel).toLowerCase();

      // 📏 SIZE BEFORE
      const originalSizeBytes = getFileSizeInBytes(inputPath);

      const outputFileName = `compressed-${Date.now()}.7z`;
      const outputPath = path.join(
        rootDir,
        'temp', 'outputs',
        outputFileName
      );

      // Call 7-Zip compression safely with Concurrency Limiter
      await globalLimiter.run(async () => {
        await compressPdf(inputPath, outputPath, compressionLevel);
      });

      // Verify output exists
      if (!fs.existsSync(outputPath)) {
        throw new Error("Output file creation failed - 7-Zip compression may have timed out or failed.");
      }

      // 📏 SIZE AFTER
      const compressedSizeBytes = getFileSizeInBytes(outputPath);

      // 📊 STATS
      const stats = {
        before: formatBytes(originalSizeBytes),
        after: formatBytes(compressedSizeBytes),
        reduction: (
          ((originalSizeBytes - compressedSizeBytes) / originalSizeBytes) *
          100
        ).toFixed(2) + '%'
      };

      console.log('PDF 7-Zip Compression stats:', stats);

      return res.json({
        success: true,
        stats,
        downloadLink: `/compress/pdf/download-file/${outputFileName}`
      });

    } catch (err) {
      console.error('Compression Error:', err);
      return res.status(500).json({ error: err.message || 'Compression failed. Please try again.' });
    } finally {
      // 🧹 STRICT CLEANUP: Always delete the input file to prevent disk leaks
      if (inputPath && fs.existsSync(inputPath)) {
        try { fs.unlinkSync(inputPath); } catch (e) { console.error("Input cleanup failed:", e); }
      }
    }
  }
);

router.get('/download-file/:fileName', (req, res) => {
  const fileName = req.params.fileName;

  // Strict alphanumeric / timestamp validation to prevent directory traversal
  if (!fileName || !/^compressed-\d+\.7z$/.test(fileName)) {
    return res.status(400).send("Invalid filename");
  }

  const outDir = path.resolve(rootDir, 'temp', 'outputs');
  const filePath = path.resolve(outDir, fileName);

  // Path containment verification
  if (!filePath.startsWith(outDir + path.sep)) {
    return res.status(403).send("Forbidden");
  }

  if (fs.existsSync(filePath)) {
    res.download(filePath, fileName, (err) => {
      if (err) {
        console.error("Download Error:", err);
      }
    });
  } else {
    res.status(404).send("File expired or not found");
  }
});

module.exports = router;
