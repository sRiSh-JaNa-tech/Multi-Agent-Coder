const express = require('express');
const path = require('path');
const fs = require('fs');
const rootDir = require("../utils/pathUtils");
const uploadPDF = require("../config/pdfConfig");
const { runPython } = require("../utils/pythonRunner");
const { validateUploadedFileSignature } = require("../utils/fileSignature");

const router = express.Router();

const PYTHON_SCRIPT = path.join(rootDir, 'python', 'scripts', 'convert_bridge.py');
const ALLOWED_MODES = ['png', 'jpg', 'jpeg', 'html', 'docx', 'txt'];

router.post('/upload', uploadPDF.single('pdf'), validateUploadedFileSignature('pdf', 'pdf'), async (req, res) => {
    let inputPath = null;
    try {
        if (!req.file) {
            return res.status(400).json({ error: 'No file uploaded' });
        }

        inputPath = req.file.path;
        const rawMode = String(req.body.format || 'png').toLowerCase().trim();
        const mode = ALLOWED_MODES.includes(rawMode) ? rawMode : 'png';

        const rawStart = parseInt(req.body.startPage, 10);
        const rawEnd = parseInt(req.body.endPage, 10);
        const startPage = Number.isInteger(rawStart) && rawStart > 0 ? rawStart : null;
        const endPage = Number.isInteger(rawEnd) && rawEnd > 0 ? rawEnd : null;

        const timestamp = Date.now();
        const outDir = path.resolve(rootDir, 'temp', 'outputs');
        if (!fs.existsSync(outDir)) fs.mkdirSync(outDir, { recursive: true });

        let outputFilename;
        if (mode === 'html') {
            outputFilename = `converted-${timestamp}.html`;
        } else if (mode === 'docx') {
            outputFilename = `converted-${timestamp}.docx`;
        } else {
            const isSinglePage = (startPage && endPage && startPage === endPage);
            if (isSinglePage) {
                outputFilename = `converted-${timestamp}.${mode}`;
            } else {
                outputFilename = `converted-${timestamp}.zip`;
            }
        }

        const outputPath = path.join(outDir, outputFilename);

        const payload = {
            inputPath,
            outputPath,
            mode,
            startPage,
            endPage
        };

        const payloadBase64 = Buffer.from(JSON.stringify(payload)).toString('base64');

        // Safe execution using execFile (zero shell command injection)
        const { stdout, stderr } = await runPython(PYTHON_SCRIPT, [payloadBase64]);

        if (stderr) {
            console.warn("Conversion Stderr:", stderr);
        }

        try {
            const response = JSON.parse(stdout);
            if (response.success) {
                return res.json({
                    success: true,
                    result: {
                        status: 'Success',
                        downloadUrl: `/convert/download?fileName=${outputFilename}`,
                        format: mode
                    }
                });
            } else {
                return res.status(500).json({ error: response.error || 'Conversion process failed' });
            }
        } catch (parseError) {
            console.error("JSON Parse Error:", parseError, "Raw output:", stdout);
            return res.status(500).json({ error: 'Failed to parse conversion result' });
        }

    } catch (err) {
        console.error("Router Catch Error:", err);
        return res.status(500).json({ error: 'Internal server error during conversion.' });
    } finally {
        if (inputPath && fs.existsSync(inputPath)) {
            try { fs.unlinkSync(inputPath); } catch (e) { }
        }
    }
});

router.get('/download', (req, res) => {
    const fileName = req.query.fileName;
    if (!fileName || !/^converted-\d+\.[a-zA-Z0-9]+$/.test(fileName)) {
        return res.status(400).send("Invalid filename");
    }

    const outDir = path.resolve(rootDir, 'temp', 'outputs');
    const filePath = path.resolve(outDir, fileName);

    if (!filePath.startsWith(outDir + path.sep)) {
        return res.status(403).send("Forbidden");
    }

    if (fs.existsSync(filePath)) {
        res.download(filePath, fileName, (err) => {
            if (err) console.error("Download Error:", err);
        });
    } else {
        res.status(404).send("File expired or not found");
    }
});

module.exports = router;
