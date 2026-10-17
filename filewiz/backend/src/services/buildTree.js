const fs = require('fs/promises');
const path = require('path');

async function buildTree(dirPath) {
  const entries = await fs.readdir(dirPath, { withFileTypes: true });
  const result = [];

  for (const entry of entries) {
    const fullPath = path.join(dirPath, entry.name);

    if (entry.isDirectory()) {
      result.push({
        name: entry.name,
        type: 'folder',
        children: await buildTree(fullPath)
      });
    } else {
      result.push({
        name: entry.name,
        type: 'file'
      });
    }
  }

  return result;
}

module.exports = buildTree;
