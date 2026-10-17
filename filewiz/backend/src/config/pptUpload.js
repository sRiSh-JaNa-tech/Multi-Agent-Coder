const multer = require('multer');
const path = require('path');
const fs = require('fs');

const rootDir = require('../utils/pathUtils');


const uploadDir = path.join(rootDir, 'temp','uploads');
if (!fs.existsSync(uploadDir)) {
  fs.mkdirSync(uploadDir, { recursive: true });
}

// Storage config
const storage = multer.diskStorage({
  destination: (req, file, cb) => {
    cb(null, uploadDir);
  },
  filename: (req, file, cb) => {
    const uniqueName =
      Date.now() + '-' + Math.round(Math.random() * 1e9);
    cb(null, uniqueName + path.extname(file.originalname));
  }
});

// File filter: PPT & PPTX only
const fileFilter = (req, file, cb) => {
  const ext = path.extname(file.originalname).toLowerCase();

  if (ext === '.ppt' || ext === '.pptx') {
    cb(null, true);
  } else {
    cb(new Error('Only PPT or PPTX files are allowed'));
  }
};

// Multer instance
const uploadPPT = multer({
  storage,
  fileFilter,
  limits: {
    fileSize: 50 * 1024 * 1024 // 50 MB limit
  }
});

module.exports = uploadPPT;
