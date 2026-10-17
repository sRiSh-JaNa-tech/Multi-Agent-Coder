const fs = require('fs');

/**
 * Validates file magic bytes to prevent polyglot file uploads and extension spoofing.
 */
function verifyMagicBytes(filePath, expectedType) {
  if (!fs.existsSync(filePath)) {
    return false;
  }

  const fd = fs.openSync(filePath, 'r');
  const buffer = Buffer.alloc(16);
  fs.readSync(fd, buffer, 0, 16, 0);
  fs.closeSync(fd);

  switch (expectedType.toLowerCase()) {
    case 'pdf': {
      // PDF files must start with %PDF- (hex: 25 50 44 46)
      const header = buffer.subarray(0, 5).toString('ascii');
      return header.startsWith('%PDF-') || header.startsWith('%PDF');
    }
    case 'zip': {
      // ZIP files start with PK\x03\x04 or PK\x05\x06
      return buffer[0] === 0x50 && buffer[1] === 0x4B &&
        ((buffer[2] === 0x03 && buffer[3] === 0x04) ||
         (buffer[2] === 0x05 && buffer[3] === 0x06) ||
         (buffer[2] === 0x07 && buffer[3] === 0x08));
    }
    case 'ppt':
    case 'pptx': {
      // PPTX is a ZIP container starting with PK\x03\x04
      const isZip = buffer[0] === 0x50 && buffer[1] === 0x4B && buffer[2] === 0x03 && buffer[3] === 0x04;
      // Legacy PPT is an OLE compound document: D0 CF 11 E0 A1 B1 1A E1
      const isOle = buffer[0] === 0xD0 && buffer[1] === 0xCF && buffer[2] === 0x11 && buffer[3] === 0xE0;
      return isZip || isOle;
    }
    default:
      return true;
  }
}

/**
 * Express middleware to validate uploaded file signature against expected type.
 */
function validateUploadedFileSignature(expectedType, fileFieldName = 'files') {
  return (req, res, next) => {
    const file = req.file || (req.files && req.files[fileFieldName] && req.files[fileFieldName][0]);
    if (!file) {
      return next();
    }

    if (!verifyMagicBytes(file.path, expectedType)) {
      try { fs.unlinkSync(file.path); } catch (e) {}
      return res.status(400).json({
        error: `File signature mismatch: Uploaded file is not a valid ${expectedType.toUpperCase()} document.`
      });
    }

    next();
  };
}

module.exports = {
  verifyMagicBytes,
  validateUploadedFileSignature
};
