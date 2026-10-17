const path = require("path");
const rootDir = require("../utils/pathUtils");
const logger = require("./logger");
const { runPython } = require("../utils/pythonRunner");

const pythonScriptPath = path.join(
  rootDir,
  "python",
  "scripts",
  "read_zip.py"
);

async function readZipWithPython(zipPath) {
  try {
    // Safe execution using execFile (zero shell command injection)
    const { stdout, stderr } = await runPython(pythonScriptPath, [zipPath]);

    if (stderr) {
      logger.log(stderr, "WARNING", "python_script");
    }

    const result = stdout.trim();
    if (!result) {
      logger.log("Python returned empty output", "WARNING", "python_exec");
      throw new Error("Empty Python output");
    }

    logger.log(
      `Python processed zip successfully: ${zipPath}`,
      "INFO",
      "python_exec"
    );

    return result;
  } catch (error) {
    logger.log(error.message, "ERROR", "python_exec");
    throw error;
  }
}

module.exports = { readZipWithPython };
