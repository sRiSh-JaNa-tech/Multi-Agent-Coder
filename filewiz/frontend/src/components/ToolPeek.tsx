import React, { useState, useEffect, useRef } from 'react';
import { Upload, Folder, FileText, AlertCircle, Save, Download, FilePlus, FolderPlus, Edit, Trash2 } from 'lucide-react';
import api from '../utils/api';

interface FileNode {
  name: string;
  type: 'folder' | 'file';
  children?: FileNode[];
}

const EDITABLE_EXTENSIONS = [
  'js', 'json', 'txt', 'md',
  'html', 'css', 'ts', 'csv'
];

function isEditable(fileName: string): boolean {
  const ext = fileName.split('.').pop()?.toLowerCase();
  return ext ? EDITABLE_EXTENSIONS.includes(ext) : false;
}

const ToolPeek: React.FC = () => {
  const [file, setFile] = useState<File | null>(null);
  const [workspaceId, setWorkspaceId] = useState<string | null>(null);
  const [tree, setTree] = useState<FileNode[]>([]);
  const [currentFilePath, setCurrentFilePath] = useState<string | null>(null);
  const [editorReadOnly, setEditorReadOnly] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  // File tree options state
  const [selectedItemPath, setSelectedItemPath] = useState<string | null>(null);
  const [expandedFolders, setExpandedFolders] = useState<Record<string, boolean>>({});

  const editorContainerRef = useRef<HTMLDivElement>(null);
  const monacoEditorRef = useRef<any>(null);

  // Load Monaco Editor
  useEffect(() => {
    if (workspaceId) {
      const script = document.createElement('script');
      script.src = 'https://cdn.jsdelivr.net/npm/monaco-editor@0.45.0/min/vs/loader.js';
      script.async = true;
      script.onload = () => {
        const win = window as any;
        win.require.config({
          paths: { vs: 'https://cdn.jsdelivr.net/npm/monaco-editor@0.45.0/min/vs' }
        });
        win.require(['vs/editor/editor.main'], () => {
          if (editorContainerRef.current) {
            monacoEditorRef.current = win.monaco.editor.create(editorContainerRef.current, {
              value: '// Select a file from the explorer to view or edit',
              language: 'plaintext',
              theme: 'vs-dark',
              automaticLayout: true,
              fontSize: 14,
              tabSize: 2,
            });
          }
        });
      };
      document.body.appendChild(script);

      return () => {
        if (monacoEditorRef.current) {
          monacoEditorRef.current.dispose();
        }
        document.body.removeChild(script);
      };
    }
  }, [workspaceId]);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      setFile(e.target.files[0]);
      setError(null);
    }
  };

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) return;

    setError(null);
    setLoading(true);

    const formData = new FormData();
    formData.append('archive', file);

    try {
      const response = await api.post('/peek/result', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });

      if (response.data.success || response.data.workspaceId) {
        setWorkspaceId(response.data.workspaceId);
        setTree(response.data.tree || []);
      } else {
        throw new Error('Processing failed');
      }
    } catch (err: any) {
      console.error('Peek zip upload error:', err);
      setError(err.response?.data?.error || 'Failed to inspect ZIP file. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const refreshTree = async () => {
    if (!workspaceId) return;
    try {
      const res = await api.get(`/peek/tree?ws=${workspaceId}`);
      setTree(res.data);
    } catch (err) {
      console.error('Refresh tree error:', err);
    }
  };

  const openFile = async (filePath: string) => {
    if (!workspaceId) return;
    setCurrentFilePath(filePath);
    setSelectedItemPath(filePath);

    try {
      const res = await api.get(`/peek/file?ws=${workspaceId}&path=${encodeURIComponent(filePath)}`);
      
      if (monacoEditorRef.current) {
        monacoEditorRef.current.setValue(res.data.content || '');
        const ext = filePath.split('.').pop() || 'plaintext';
        const win = window as any;
        win.monaco.editor.setModelLanguage(
          monacoEditorRef.current.getModel(),
          ext === 'js' ? 'javascript' : ext === 'ts' ? 'typescript' : ext
        );

        const editable = isEditable(filePath);
        setEditorReadOnly(!editable);
        monacoEditorRef.current.updateOptions({ readOnly: !editable });
      }
    } catch (err: any) {
      console.error('Open file error:', err);
      setError('Failed to load file contents.');
    }
  };

  const handleSaveFile = async () => {
    if (!workspaceId || !currentFilePath || !monacoEditorRef.current) return;

    try {
      const content = monacoEditorRef.current.getValue();
      const res = await api.post('/peek/file/save', {
        ws: workspaceId,
        path: currentFilePath,
        content
      });

      if (res.data.success) {
        alert('File saved successfully!');
      } else {
        throw new Error('Save failed');
      }
    } catch (err) {
      console.error('Save file error:', err);
      alert('Failed to save file edits.');
    }
  };

  const handleCreateFile = async () => {
    if (!workspaceId) return;
    const name = prompt('Enter new file name:');
    if (!name) return;

    const baseDir = selectedItemPath && selectedItemPath.includes('.') 
      ? selectedItemPath.substring(0, selectedItemPath.lastIndexOf('/')) 
      : selectedItemPath || '';

    const newPath = baseDir ? `${baseDir}/${name}` : name;

    try {
      await api.post('/peek/file/create', { ws: workspaceId, path: newPath });
      await refreshTree();
      openFile(newPath);
    } catch (err: any) {
      alert('Error creating file: ' + (err.response?.data?.error || err.message));
    }
  };

  const handleCreateFolder = async () => {
    if (!workspaceId) return;
    const name = prompt('Enter new folder name:');
    if (!name) return;

    const baseDir = selectedItemPath && selectedItemPath.includes('.') 
      ? selectedItemPath.substring(0, selectedItemPath.lastIndexOf('/')) 
      : selectedItemPath || '';

    const newPath = baseDir ? `${baseDir}/${name}` : name;

    try {
      await api.post('/peek/folder/create', { ws: workspaceId, path: newPath });
      await refreshTree();
    } catch (err: any) {
      alert('Error creating folder: ' + (err.response?.data?.error || err.message));
    }
  };

  const handleRenameItem = async () => {
    if (!workspaceId || !selectedItemPath) return;
    const newName = prompt('Enter new name:');
    if (!newName) return;

    const parentPath = selectedItemPath.includes('/')
      ? selectedItemPath.substring(0, selectedItemPath.lastIndexOf('/'))
      : '';
    const newPath = parentPath ? `${parentPath}/${newName}` : newName;

    try {
      await api.post('/peek/rename', { ws: workspaceId, oldPath: selectedItemPath, newPath });
      await refreshTree();
      setSelectedItemPath(newPath);
      if (currentFilePath === selectedItemPath) {
        setCurrentFilePath(newPath);
      }
    } catch (err: any) {
      alert('Error renaming: ' + (err.response?.data?.error || err.message));
    }
  };

  const handleDeleteItem = async () => {
    if (!workspaceId || !selectedItemPath) return;
    if (!confirm(`Are you sure you want to delete ${selectedItemPath}?`)) return;

    try {
      await api.post('/peek/delete', { ws: workspaceId, path: selectedItemPath });
      await refreshTree();
      setSelectedItemPath(null);
      if (currentFilePath === selectedItemPath) {
        setCurrentFilePath(null);
        if (monacoEditorRef.current) {
          monacoEditorRef.current.setValue('// File deleted');
        }
      }
    } catch (err: any) {
      alert('Error deleting: ' + (err.response?.data?.error || err.message));
    }
  };

  const handleDownload = () => {
    if (!workspaceId) return;
    window.location.href = `http://localhost:3000/peek/download?ws=${workspaceId}`;
  };

  const toggleFolder = (folderPath: string) => {
    setExpandedFolders(prev => ({
      ...prev,
      [folderPath]: !prev[folderPath]
    }));
    setSelectedItemPath(folderPath);
  };

  // Render tree node recursive component
  const renderNode = (node: FileNode, prefix = '') => {
    const fullPath = prefix ? `${prefix}/${node.name}` : node.name;
    const isFolder = node.type === 'folder';

    if (isFolder) {
      const isOpen = !!expandedFolders[fullPath];
      return (
        <div key={fullPath} className="text-sm">
          <div
            onClick={() => toggleFolder(fullPath)}
            className={`flex items-center gap-1.5 py-1 px-2 rounded-lg cursor-pointer hover:bg-slate-100 font-semibold ${
              selectedItemPath === fullPath ? 'bg-blue-50 text-blue-700' : 'text-blue-600'
            }`}
          >
            <span>{isOpen ? '▼' : '▶'}</span>
            <Folder className="w-4 h-4 text-blue-500 fill-blue-100" />
            <span className="truncate">{node.name}</span>
          </div>
          {isOpen && node.children && (
            <div className="pl-4 border-l border-slate-200/60 ml-2.5 mt-0.5 space-y-0.5">
              {node.children.map((child) => renderNode(child, fullPath))}
            </div>
          )}
        </div>
      );
    } else {
      return (
        <div
          key={fullPath}
          onClick={() => openFile(fullPath)}
          className={`flex items-center gap-2 py-1.5 px-3 rounded-lg cursor-pointer text-xs font-medium hover:bg-slate-150 transition ${
            selectedItemPath === fullPath
              ? 'bg-blue-100 text-blue-700 font-bold'
              : 'text-slate-600 hover:text-slate-800'
          }`}
        >
          <FileText className="w-3.5 h-3.5 text-slate-400" />
          <span className="truncate">{node.name}</span>
        </div>
      );
    }
  };

  const resetTool = () => {
    setFile(null);
    setWorkspaceId(null);
    setTree([]);
    setCurrentFilePath(null);
    setSelectedItemPath(null);
    setError(null);
  };

  return (
    <div className="flex-1 flex flex-col h-[calc(100vh-4rem)]">
      {!workspaceId ? (
        <div className="flex-1 flex items-center justify-center p-6 bg-slate-50">
          <div className="w-full max-w-xl bg-white rounded-3xl shadow-xl p-8 border border-slate-100">
            <h2 className="text-3xl font-black text-center text-slate-800 font-display">
              X-Ray ZIP Peek
            </h2>
            <p className="text-center text-slate-500 mt-2 text-sm">
              Inspect zip internals, modify source files, and download the rebuilt archive securely
            </p>

            {error && (
              <div className="mt-6 flex items-center gap-2 bg-rose-50 border border-rose-200 text-rose-600 px-4 py-3 rounded-xl text-center text-sm font-medium">
                <AlertCircle className="w-5 h-5 flex-shrink-0" />
                <span>{error}</span>
              </div>
            )}

            <form onSubmit={handleUpload} className="mt-8 space-y-6">
              <div className="flex flex-col items-center justify-center w-full h-48 border-2 border-dashed border-slate-300 bg-slate-50 rounded-2xl cursor-pointer hover:bg-slate-100/50 transition">
                <input
                  id="zip-file"
                  type="file"
                  accept=".zip"
                  onChange={handleFileChange}
                  className="hidden"
                  required
                />
                <label htmlFor="zip-file" className="flex flex-col items-center justify-center w-full h-full cursor-pointer">
                  <Upload className="w-10 h-10 mb-3 text-slate-400" />
                  <div className="text-center px-4">
                    {file ? (
                      <>
                        <p className="text-slate-700 font-bold flex items-center justify-center gap-1.5">
                          <FileText className="w-4 h-4 text-blue-500" />
                          {file.name}
                        </p>
                        <p className="text-xs text-slate-400 mt-1">
                          {(file.size / (1024 * 1024)).toFixed(2)} MB
                        </p>
                      </>
                    ) : (
                      <>
                        <p className="text-slate-700 font-medium">Drag & drop your ZIP file</p>
                        <p className="text-xs text-slate-400 mt-1">or click to browse</p>
                      </>
                    )}
                  </div>
                </label>
              </div>

              <button
                type="submit"
                disabled={!file || loading}
                className="w-full bg-blue-600 hover:bg-blue-700 text-white py-3.5 rounded-xl font-bold transition shadow-lg flex items-center justify-center gap-2 disabled:opacity-50"
              >
                {loading ? 'Analyzing ZIP...' : 'Inspect ZIP Archive'}
              </button>
            </form>
          </div>
        </div>
      ) : (
        <div className="flex-1 flex flex-col lg:flex-row overflow-hidden bg-slate-100/40">
          {/* File Tree Sidebar */}
          <aside className="w-full lg:w-72 bg-white border-b lg:border-b-0 lg:border-r border-slate-200 flex flex-col shrink-0 min-h-0">
            <div className="px-5 py-4 border-b border-slate-150">
              <h3 className="text-xs font-black text-slate-800 uppercase tracking-wider">Workspace Explorer</h3>
            </div>
            
            {/* Tree Navigation */}
            <div className="flex-1 overflow-y-auto p-4 space-y-1 select-none min-h-[200px]">
              {tree.map((node) => renderNode(node))}
            </div>

            {/* Tree Modification Actions */}
            <div className="p-4 border-t border-slate-150 grid grid-cols-2 gap-2 bg-slate-50">
              <button
                onClick={handleCreateFile}
                className="flex items-center justify-center gap-1.5 py-2 text-xs font-bold text-slate-600 hover:text-slate-800 border border-slate-200 bg-white rounded-xl shadow-sm"
              >
                <FilePlus className="w-3.5 h-3.5 text-blue-500" />
                <span>+ File</span>
              </button>
              <button
                onClick={handleCreateFolder}
                className="flex items-center justify-center gap-1.5 py-2 text-xs font-bold text-slate-600 hover:text-slate-800 border border-slate-200 bg-white rounded-xl shadow-sm"
              >
                <FolderPlus className="w-3.5 h-3.5 text-blue-500" />
                <span>+ Folder</span>
              </button>
              <button
                onClick={handleRenameItem}
                disabled={!selectedItemPath}
                className="flex items-center justify-center gap-1.5 py-2 text-xs font-bold text-slate-600 hover:text-slate-800 border border-slate-200 bg-white rounded-xl shadow-sm disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <Edit className="w-3.5 h-3.5" />
                <span>Rename</span>
              </button>
              <button
                onClick={handleDeleteItem}
                disabled={!selectedItemPath}
                className="flex items-center justify-center gap-1.5 py-2 text-xs font-bold text-rose-600 hover:text-rose-700 border border-rose-200 bg-rose-50/50 rounded-xl shadow-sm disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <Trash2 className="w-3.5 h-3.5" />
                <span>Delete</span>
              </button>
            </div>
          </aside>

          {/* Monaco Editor Container */}
          <section className="flex-1 flex flex-col min-h-0 bg-slate-900">
            {/* Editor Toolbar */}
            <div className="flex items-center justify-between border-b border-slate-800 px-6 py-3 bg-slate-950 text-white shrink-0">
              <span className="text-xs font-bold text-slate-400 truncate max-w-[300px]">
                {currentFilePath ? `Editing: ${currentFilePath}` : 'No file selected'}
                {currentFilePath && editorReadOnly && ' (read-only)'}
              </span>

              <div className="flex items-center gap-3">
                <button
                  onClick={handleSaveFile}
                  disabled={editorReadOnly || !currentFilePath}
                  className="flex items-center gap-1.5 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-800 disabled:text-slate-500 text-white px-4 py-2 rounded-xl text-xs font-bold transition shadow"
                >
                  <Save className="w-3.5 h-3.5" />
                  <span>Save</span>
                </button>

                <button
                  onClick={handleDownload}
                  className="flex items-center gap-1.5 bg-green-600 hover:bg-green-700 text-white px-4 py-2 rounded-xl text-xs font-bold transition shadow"
                >
                  <Download className="w-3.5 h-3.5" />
                  <span>Download ZIP</span>
                </button>

                <button
                  onClick={resetTool}
                  className="text-xs font-bold text-slate-400 hover:text-white px-3 py-2 rounded-xl border border-slate-800 hover:border-slate-700 transition"
                >
                  Close
                </button>
              </div>
            </div>

            {/* Monaco Container */}
            <div ref={editorContainerRef} className="flex-1 min-h-0 w-full" style={{ height: 'calc(100% - 3.5rem)' }} />
          </section>
        </div>
      )}
    </div>
  );
};

export default ToolPeek;
