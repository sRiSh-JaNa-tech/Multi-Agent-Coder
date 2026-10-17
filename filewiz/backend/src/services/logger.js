const fs = require("fs");
const path = require("path");
const rootDir = require("../utils/pathUtils");

// Resolve the log path safely
const LOG_FILE_PATH = path.join(rootDir, "logs", "file.log");


if (!fs.existsSync(path.join(rootDir, "logs"))) {
    fs.mkdirSync(path.join(rootDir, "logs"), { recursive: true });
}

async function trimLogFile() {
    try {
        const data = await fs.promises.readFile(LOG_FILE_PATH, "utf8");
        const lines = data.split("\n").filter(line => line.trim() !== "");
        
        if (lines.length > 50) {
            const trimmedData = lines.slice(-50).join("\n") + "\n";
            await fs.promises.writeFile(LOG_FILE_PATH, trimmedData, "utf8");
        }
    } catch (err) {
        // Use console.error so we don't get into an infinite loop of logging errors
        console.error("Failed to trim log file:", err.message);
    }
}

/**
 * Main log function
 */
const log = async (message, level = "DEBUG", module_name = "app") => {
    const time = new Date().toISOString().replace('T', ' ').split('.')[0];
    const logType = level.toUpperCase();
    const logEntry = `[${time}] [${module_name}] ${logType}: ${message}\n`;

    try {
        await fs.promises.appendFile(LOG_FILE_PATH, logEntry, "utf8");
        await trimLogFile();
    } catch (err) {
        console.error("Logging failed:", err);
    }
};

module.exports = { 'log' : log };