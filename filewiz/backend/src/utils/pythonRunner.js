const { execFile } = require('child_process');

function getPythonBin() {
  return process.env.PYTHON_BIN || 'python';
}

/**
 * Executes a Python script safely using execFile without an intermediate shell.
 * Prevents Remote Code Execution (RCE) via command injection.
 */
function runPython(scriptPath, args = [], options = {}) {
  return new Promise((resolve, reject) => {
    const pythonBin = getPythonBin();
    const execOptions = {
      maxBuffer: 10 * 1024 * 1024,
      ...options,
      shell: false // CRITICAL: Do NOT spawn a shell
    };

    execFile(pythonBin, [scriptPath, ...args], execOptions, (err, stdout, stderr) => {
      if (err) {
        err.stdout = stdout;
        err.stderr = stderr;
        return reject(err);
      }
      resolve({ stdout, stderr });
    });
  });
}

module.exports = { getPythonBin, runPython };
