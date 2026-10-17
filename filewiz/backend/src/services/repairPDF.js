const fs = require("fs");
const { execFile } = require("child_process");

const path = require("path");
const { runPython } = require("../utils/pythonRunner");

function findBinary(name, fallbackPaths = []) {
  for (const p of fallbackPaths) {
    if (fs.existsSync(p)) return p;
  }
  return name; // rely on PATH
}

const QPDF_BIN = findBinary("qpdf", ["C:\\qpdf\\bin\\qpdf.exe", "/usr/bin/qpdf"]);

function execFileCmd(bin, args) {
  return new Promise((resolve, reject) => {
    // shell: false strictly prevents command injection
    execFile(bin, args, { shell: false }, (err, stdout, stderr) => {
      // qpdf --check returns exit code 3 for warnings, which we should allow
      if (err && err.code !== 3) {
        reject(stderr || stdout || err);
      } else {
        resolve({ stdout, stderr, code: err ? err.code : 0 });
      }
    });
  });
}

/* 1️⃣ Detect corruption */
async function checkCorruption(pdfPath) {
  try {
    await execFileCmd(QPDF_BIN, ["--check", pdfPath]);
    return { type: "none", severity: "none" };
  } catch (err) {
    const error = String(err).toLowerCase();

    if (error.includes("xref")) return { type: "xref", severity: "medium" };
    if (error.includes("trailer")) return { type: "trailer", severity: "medium" };
    if (error.includes("unexpected eof")) return { type: "truncated", severity: "critical" };

    return { type: "unknown", severity: "high" };
  }
}

/* 2️⃣ Get Page Count */
async function getPageCount(pdfPath) {
  try {
    const { stdout } = await execFileCmd(QPDF_BIN, ["--show-npages", pdfPath]);
    return parseInt(stdout.trim()) || 0;
  } catch {
    return 0;
  }
}

/* 3️⃣ Repair using qpdf */
async function repairQPDF(input, output) {
  await execFileCmd(QPDF_BIN, ["--linearize", input, output]);
  return "qpdf";
}

/* 4️⃣ Repair using PyMuPDF (C-level xref and dictionary reconstruction) */
async function repairPyMuPDF(input, output) {
  const script = path.join(__dirname, "../python/scripts/repair_pymupdf.py");
  await runPython(script, [input, output]);
  return "pymupdf";
}

/* 5️⃣ Validate repaired file */
async function validatePDF(path) {
  try {
    await execFileCmd(QPDF_BIN, ["--check", path]);
    return true;
  } catch (err) {
    return (err && err.code === 3);
  }
}

/* 6️⃣ Confidence + Label Engine */
function calculateResult(method, severity, valid) {
  if (!method || !valid) {
    return { label: "Unrecoverable", confidence: 0 };
  }

  if (method === "qpdf") {
    return { label: "Fully repaired", confidence: 92 };
  }

  let confidence = 70;
  if (severity === "critical") confidence -= 25;
  if (severity === "high") confidence -= 15;
  confidence = Math.max(confidence, 40);

  return {
    label: confidence >= 70 ? "Partially recovered" : "Unrecoverable",
    confidence
  };
}

/* 🚀 MAIN PIPELINE */
async function processPDF(inputPath, outputPath) {
  const detection = await checkCorruption(inputPath);

  // Try qpdf first
  try {
    const method = await repairQPDF(inputPath, outputPath);
    const valid = await validatePDF(outputPath);
    const pages = await getPageCount(valid ? outputPath : inputPath);

    const { label, confidence } = calculateResult(
      method,
      detection.severity,
      valid
    );

    return { detection, method, label, confidence, pages };
  } catch { }

  // Fallback to PyMuPDF
  try {
    const method = await repairPyMuPDF(inputPath, outputPath);
    const valid = await validatePDF(outputPath);
    const pages = await getPageCount(valid ? outputPath : inputPath);

    const { label, confidence } = calculateResult(
      method,
      detection.severity,
      valid
    );

    return { detection, method, label, confidence, pages };
  } catch { }

  return {
    detection,
    method: null,
    label: "Unrecoverable",
    confidence: 0,
    pages: 0
  };
}

module.exports = { processPDF };