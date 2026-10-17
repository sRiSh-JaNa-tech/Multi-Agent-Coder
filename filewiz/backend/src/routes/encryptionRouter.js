const express = require('express');
const path = require('path');
const fs = require('fs');

const rootDir = require("../utils/pathUtils");
const uploadPDF = require("../config/pdfConfig");
const { runPython } = require("../utils/pythonRunner");
const { validateUploadedFileSignature } = require("../utils/fileSignature");

const router = express.Router();

router.post('/upload',
    uploadPDF.single('pdf'),
    validateUploadedFileSignature('pdf', 'pdf'),
    async (req, res) => {
        let inputPath = null;
        try {
            if (!req.file) {
                return res.status(400).json({ error: 'No file uploaded' });
            }

            inputPath = req.file.path;
            const user_password = req.body.user_password || '';
            const owner_password = req.body.owner_password || '';
            const rawLevel = req.body.encryption_level || '128';
            const encryption_lvl = ['40', '128', '256'].includes(String(rawLevel))
                ? String(rawLevel)
                : '128';

            const outputFileName = `encrypted-${Date.now()}.pdf`;
            const outDir = path.resolve(rootDir, 'temp', 'outputs');

            if (!fs.existsSync(outDir)) {
                fs.mkdirSync(outDir, { recursive: true });
            }

            const outputPath = path.join(outDir, outputFileName);
            const pythonScript = path.join(
                rootDir, 'python', 'scripts', 'pdf_encryption.py'
            );

            const payload = {
                user_password,
                owner_password,
                encryption_lvl,
                inputPath,
                outputPath
            };
            const payloadBase64 = Buffer.from(JSON.stringify(payload)).toString('base64');

            // Safe execution using execFile (zero shell command injection)
            const { stdout, stderr } = await runPython(pythonScript, [payloadBase64]);

            if (stderr) {
                console.warn("Encryption Stderr:", stderr);
            }
            console.log("Encryption success:", stdout);

            return res.json({
                success: true,
                downloadLink: `/encrypt/download?fileName=${outputFileName}`
            });

        } catch (err) {
            console.error("Encryption Execution Error:", err);
            return res.status(500).json({ error: 'Encryption failed. Please ensure the PDF is valid.' });
        } finally {
            if (inputPath && fs.existsSync(inputPath)) {
                try { fs.unlinkSync(inputPath); } catch (e) { console.error("Input clean failed", e); }
            }
        }
    }
);

router.get('/download', (req, res) => {
    const fileName = req.query.fileName;
    if (!fileName || !/^encrypted-\d+\.pdf$/.test(fileName)) {
        return res.status(400).send("Invalid file name");
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
        res.status(404).send("File not found or expired");
    }
});

module.exports = router;