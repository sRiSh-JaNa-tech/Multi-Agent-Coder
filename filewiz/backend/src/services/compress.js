const path = require('path');
const sevenZip = require('7zip-bin');
const rootDir = require("../utils/pathUtils");
const { runPython } = require("../utils/pythonRunner");

const pythonScript = path.join(
  rootDir,
  'python', 'scripts', 'pdf_Compress.py'
);

const ALLOWED_COMPRESSION_LEVELS = ['low', 'normal', 'extreme', 'high'];

async function compressPdf(inputPath, outputPath, level = 'normal') {
  const safeLevel = ALLOWED_COMPRESSION_LEVELS.includes(String(level).toLowerCase())
    ? String(level).toLowerCase()
    : 'normal';

  const env = {
    ...process.env,
    SEVEN_ZIP_PATH: sevenZip.path7za || process.env.SEVEN_ZIP_PATH || ''
  };

  const { stdout, stderr } = await runPython(
    pythonScript,
    [inputPath, outputPath, safeLevel],
    { env }
  );

  if (stderr) {
    console.warn('7-Zip Compression Stderr:', stderr);
  }
  console.log('7-Zip Compression Stdout:', stdout);
  return stdout;
}

module.exports = compressPdf;
