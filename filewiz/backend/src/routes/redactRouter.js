const express = require("express");
const path = require("path");
const fs = require("fs");
const rootDir = require("../utils/pathUtils");
const uploadPDF = require("../config/pdfConfig");
const { runPython } = require("../utils/pythonRunner");
const { validateUploadedFileSignature } = require("../utils/fileSignature");

const router = express.Router();

router.post("/upload", uploadPDF.single("pdf"), validateUploadedFileSignature('pdf', 'pdf'), (req, res) => {
  if (!req.file) {
    return res.status(400).send("No file uploaded");
  }
  res.json({ filename: req.file.filename });
});

router.post("/redact", async (req, res) => {
  const { filename, redactions } = req.body;
  if (!filename || !redactions) {
    return res.status(400).send("Missing filename or redactions");
  }

  // Prevent directory traversal
  const safeFilename = path.basename(filename);
  const inputDir = path.resolve(rootDir, "temp", "uploads");
  const inputPath = path.resolve(inputDir, safeFilename);

  if (!inputPath.startsWith(inputDir + path.sep) || !fs.existsSync(inputPath)) {
    return res.status(404).send("File not found or expired");
  }

  const outDir = path.resolve(rootDir, "temp", "redacted");
  if (!fs.existsSync(outDir)) {
    fs.mkdirSync(outDir, { recursive: true });
  }

  const outputName = `redacted-${Date.now()}.pdf`;
  const outputPath = path.join(outDir, outputName);

  const scriptPath = path.join(
    rootDir,
    "python",
    "scripts",
    "pdf_redact_coords.py"
  );

  const redactionsBase64 = Buffer.from(JSON.stringify(redactions)).toString('base64');

  try {
    // Safe execution using execFile (zero shell command injection)
    await runPython(scriptPath, [inputPath, outputPath, redactionsBase64]);

    res.download(outputPath, "redacted.pdf", () => {
      // Cleanup files
      try { if (fs.existsSync(outputPath)) fs.unlinkSync(outputPath); } catch (e) {}
      try { if (fs.existsSync(inputPath)) fs.unlinkSync(inputPath); } catch (e) {}
    });
  } catch (err) {
    console.error("Redaction execution failed:", err);
    return res.status(500).send("Redaction failed");
  }
});

module.exports = router;