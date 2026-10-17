const express = require('express');
const path = require('path');
const fs = require('fs');
const rootDir = require("../utils/pathUtils");
const uploadPDF = require("../config/pdfConfig");
const { processPDF } = require("../services/repairPDF");

const router = express.Router();

router.post('/upload',
  uploadPDF.single('pdf'),
  async (req, res) => {
    try {
      if (!req.file) {
        return res.status(400).json({ error: 'No file uploaded' });
      }

      if (req.file.mimetype !== 'application/pdf') {
        if (fs.existsSync(req.file.path)) fs.unlinkSync(req.file.path);
        return res.status(400).json({ error: 'Only PDF files are supported' });
      }

      const inputPath = req.file.path;
      const outputFileName = `repaired-${Date.now()}.pdf`;
      const outDir = path.join(rootDir, 'temp', 'outputs');
      if (!fs.existsSync(outDir)) fs.mkdirSync(outDir, { recursive: true });

      const outputPath = path.join(outDir, outputFileName);

      // Core processing
      const resultData = await processPDF(inputPath, outputPath);

      // Cleanup input
      if (fs.existsSync(inputPath)) fs.unlink(inputPath, () => { });

      const result = {
        fileName: req.file.originalname,
        fileSize: Math.round(req.file.size / 1024),
        pages: resultData.pages || 0,
        corruptionType: (resultData.detection?.type || 'UNKNOWN').toUpperCase(),
        repairMethod: (resultData.method || 'NONE').toUpperCase(),
        status: resultData.label || 'Unrecoverable',
        confidence: resultData.confidence ?? 0,
        downloadUrl: resultData.method
          ? `/repair/download?fileName=${outputFileName}`
          : null
      };

      return res.json({
        success: true,
        result
      });

    } catch (err) {
      console.error("Repair Router Error:", err);
      return res.status(500).json({ error: 'An unexpected internal error occurred during PDF processing.' });
    }
  }
);

router.get('/download', (req, res) => {
  const { fileName } = req.query;

  if (!fileName || fileName.includes('..') || fileName.includes('/') || fileName.includes('\\')) {
    return res.status(400).send("Invalid file name");
  }

  const filePath = path.join(rootDir, 'temp', 'outputs', fileName);

  if (!fs.existsSync(filePath)) {
    return res.status(404).send('File not found or expired.');
  }

  res.download(filePath, fileName, (err) => {
    if (!err) {
      // Cleanup after a delay
      setTimeout(() => {
        if (fs.existsSync(filePath)) fs.unlink(filePath, () => { });
      }, 2 * 60 * 1000); // 2 minutes
    }
  });
});

module.exports = router;