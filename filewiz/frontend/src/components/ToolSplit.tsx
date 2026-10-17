import React, { useState } from 'react';
import { Upload, FileText, AlertCircle, Scissors, Download } from 'lucide-react';
import api from '../utils/api';

interface SplitFile {
  name: string;
  path: string;
  previewUrl: string;
}

const ToolSplit: React.FC = () => {
  const [file, setFile] = useState<File | null>(null);
  const [splitMode, setSplitMode] = useState<'range' | 'count'>('range');
  const [ranges, setRanges] = useState('');
  const [parts, setParts] = useState('2');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [splitFiles, setSplitFiles] = useState<SplitFile[]>([]);
  const [selectedPaths, setSelectedPaths] = useState<string[]>([]);
  const [downloading, setDownloading] = useState(false);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      setFile(e.target.files[0]);
      setError(null);
      setSplitFiles([]);
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      setFile(e.dataTransfer.files[0]);
      setError(null);
      setSplitFiles([]);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) {
      setError('Please select a file.');
      return;
    }

    if (splitMode === 'range' && !ranges) {
      setError('Please specify page ranges (e.g. 1-2, 3-5).');
      return;
    }

    setError(null);
    setLoading(true);

    const formData = new FormData();
    formData.append('pdf', file);
    formData.append('splitMode', splitMode);
    if (splitMode === 'range') {
      formData.append('ranges', ranges);
    } else {
      formData.append('parts', parts);
    }

    try {
      const response = await api.post('/split/pdf/result', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });

      if (response.data.success) {
        setSplitFiles(response.data.splitFiles);
        // Default select all
        setSelectedPaths(response.data.splitFiles.map((f: SplitFile) => f.path));
      } else {
        throw new Error('Split process failed');
      }
    } catch (err: any) {
      console.error('Split error:', err);
      setError(err.response?.data?.error || 'Failed to split PDF. Please verify page ranges.');
    } finally {
      setLoading(false);
    }
  };

  const toggleSelectFile = (path: string) => {
    setSelectedPaths((prev) =>
      prev.includes(path) ? prev.filter((p) => p !== path) : [...prev, path]
    );
  };

  const handleDownloadSelected = async () => {
    if (selectedPaths.length === 0) {
      setError('Please select at least one file to download.');
      return;
    }

    setDownloading(true);
    setError(null);

    try {
      // Send selectedFiles as post body and expect a binary blob back
      const response = await api.post('/split/pdf/download', {
        selectedFiles: selectedPaths
      }, {
        responseType: 'blob'
      });

      const blob = new Blob([response.data], { type: 'application/zip' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'split_files.zip';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
    } catch (err: any) {
      console.error('Zip download error:', err);
      setError('Failed to create ZIP archive. Try again.');
    } finally {
      setDownloading(false);
    }
  };

  const resetTool = () => {
    setFile(null);
    setSplitFiles([]);
    setSelectedPaths([]);
    setError(null);
  };

  return (
    <div className="flex-1 flex items-center justify-center py-12 px-4 bg-slate-50">
      <div className="w-full max-w-2xl bg-white rounded-3xl shadow-xl p-8 border border-slate-100">
        <h2 className="text-3xl font-black text-center text-slate-800">
          Split Pages
        </h2>
        <p className="text-center text-slate-500 mt-2 text-sm">
          Extract specific pages or partition documents into separate files
        </p>

        {error && (
          <div className="mt-6 flex items-center gap-2 bg-rose-50 border border-rose-200 text-rose-600 px-4 py-3 rounded-xl text-center text-sm font-medium">
            <AlertCircle className="w-5 h-5 flex-shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {loading ? (
          <div className="text-center py-12 space-y-4">
            <div className="relative w-16 h-16 mx-auto">
              <div className="animate-spin rounded-full h-16 w-16 border-t-2 border-b-2 border-blue-600"></div>
              <Scissors className="w-6 h-6 text-blue-600 absolute inset-0 m-auto" />
            </div>
            <p className="text-blue-700 font-bold animate-pulse text-sm">
              Slicing PDF layers and generating previews...
            </p>
          </div>
        ) : splitFiles.length > 0 ? (
          <div className="mt-8 space-y-6">
            <div className="flex justify-between items-center bg-slate-50 p-4 rounded-xl border border-slate-200">
              <span className="text-sm font-bold text-slate-700">
                Split PDF Pages ({splitFiles.length} generated)
              </span>
              <button
                onClick={() => {
                  if (selectedPaths.length === splitFiles.length) {
                    setSelectedPaths([]);
                  } else {
                    setSelectedPaths(splitFiles.map((f) => f.path));
                  }
                }}
                className="text-xs font-bold text-blue-600 hover:text-blue-700 uppercase tracking-wider"
              >
                {selectedPaths.length === splitFiles.length ? 'Deselect All' : 'Select All'}
              </button>
            </div>

            {/* Split List */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 max-h-[300px] overflow-y-auto pr-1">
              {splitFiles.map((f, idx) => (
                <div
                  key={f.path}
                  onClick={() => toggleSelectFile(f.path)}
                  className={`border rounded-2xl p-4 flex items-center justify-between cursor-pointer transition-all hover:bg-slate-50 ${
                    selectedPaths.includes(f.path)
                      ? 'border-blue-500 bg-blue-50/10'
                      : 'border-slate-200 bg-white'
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl bg-blue-50 flex items-center justify-center text-xs font-extrabold text-blue-600 border border-blue-100">
                      #{idx + 1}
                    </div>
                    <div className="flex flex-col text-left">
                      <span className="text-xs font-bold text-slate-800 truncate max-w-[150px]">{f.name}</span>
                      <span className="text-[10px] text-slate-400">PDF Document</span>
                    </div>
                  </div>
                  <input
                    type="checkbox"
                    checked={selectedPaths.includes(f.path)}
                    onChange={() => {}} // Controlled by outer div click
                    className="w-4.5 h-4.5 rounded text-blue-600 border-slate-300 pointer-events-none"
                  />
                </div>
              ))}
            </div>

            {/* Download Selected Button */}
            <div className="bg-green-50 border border-green-200 text-green-700 p-6 rounded-2xl text-center space-y-4">
              <div className="text-xs font-semibold uppercase tracking-wider text-green-600">
                Selected {selectedPaths.length} of {splitFiles.length} files
              </div>
              <button
                onClick={handleDownloadSelected}
                disabled={selectedPaths.length === 0 || downloading}
                className="w-full text-center bg-green-600 hover:bg-green-700 disabled:bg-slate-300 disabled:cursor-not-allowed text-white py-3.5 rounded-xl font-bold transition shadow-lg hover:shadow-xl flex items-center justify-center gap-2"
              >
                <Download className="w-5 h-5" />
                <span>{downloading ? 'Creating ZIP...' : 'Download Selected as ZIP'}</span>
              </button>
            </div>

            <button
              onClick={resetTool}
              className="block w-full text-center text-sm font-bold text-slate-400 hover:text-slate-600 uppercase tracking-widest"
            >
              Split another file
            </button>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="mt-8 space-y-6">
            {/* Drag & Drop Zone */}
            <div
              onDragOver={handleDragOver}
              onDrop={handleDrop}
              className={`flex flex-col items-center justify-center w-full h-48 border-2 border-dashed rounded-2xl cursor-pointer transition-all ${
                file
                  ? 'border-blue-300 bg-blue-50/10'
                  : 'border-slate-300 bg-slate-50 hover:bg-slate-100/50'
              }`}
            >
              <input
                id="pdf-file"
                type="file"
                accept=".pdf"
                className="hidden"
                onChange={handleFileChange}
              />
              <label htmlFor="pdf-file" className="flex flex-col items-center justify-center w-full h-full cursor-pointer">
                <Upload className={`w-10 h-10 mb-3 ${file ? 'text-blue-500' : 'text-slate-400'}`} />
                <div className="text-center px-4">
                  {file ? (
                    <>
                      <p className="text-slate-700 font-bold flex items-center justify-center gap-1.5">
                        <FileText className="w-4 h-4 text-blue-500" />
                        {file.name}
                      </p>
                      <p className="text-xs text-slate-400 mt-1 font-semibold">
                        {(file.size / (1024 * 1024)).toFixed(2)} MB
                      </p>
                    </>
                  ) : (
                    <>
                      <p className="text-slate-700 font-medium">
                        Drag & drop your PDF here
                      </p>
                      <p className="text-xs text-slate-400 mt-1">
                        or click to browse files
                      </p>
                    </>
                  )}
                </div>
              </label>
            </div>

            {/* Split Mode Selector */}
            <div className="grid grid-cols-2 gap-4">
              <button
                type="button"
                onClick={() => setSplitMode('range')}
                className={`py-3 px-4 rounded-xl font-bold border transition-all text-sm ${
                  splitMode === 'range'
                    ? 'border-blue-500 bg-blue-50 text-blue-700'
                    : 'border-slate-200 bg-white text-slate-600 hover:border-slate-300'
                }`}
              >
                Split by Ranges
              </button>
              <button
                type="button"
                onClick={() => setSplitMode('count')}
                className={`py-3 px-4 rounded-xl font-bold border transition-all text-sm ${
                  splitMode === 'count'
                    ? 'border-blue-500 bg-blue-50 text-blue-700'
                    : 'border-slate-200 bg-white text-slate-600 hover:border-slate-300'
                }`}
              >
                Split into Equal Parts
              </button>
            </div>

            {/* Settings Inputs */}
            {splitMode === 'range' ? (
              <div>
                <label className="block text-xs font-bold text-slate-400 uppercase tracking-widest mb-2">
                  Define Page Ranges
                </label>
                <input
                  type="text"
                  value={ranges}
                  onChange={(e) => setRanges(e.target.value)}
                  placeholder="e.g. 1-2, 3-5, 6"
                  className="w-full px-4 py-3 border border-slate-200 rounded-xl focus:ring-2 focus:ring-blue-500 focus:outline-none transition-all text-sm font-medium"
                />
                <p className="text-[10px] text-slate-400 mt-1.5 font-semibold">
                  Separate ranges with commas. Example: "1-3, 4" will yield two documents.
                </p>
              </div>
            ) : (
              <div>
                <label className="block text-xs font-bold text-slate-400 uppercase tracking-widest mb-2">
                  Number of Equal Parts
                </label>
                <input
                  type="number"
                  min="2"
                  max="50"
                  value={parts}
                  onChange={(e) => setParts(e.target.value)}
                  className="w-full px-4 py-3 border border-slate-200 rounded-xl focus:ring-2 focus:ring-blue-500 focus:outline-none transition-all text-sm font-medium"
                />
              </div>
            )}

            <button
              type="submit"
              disabled={!file}
              className="w-full bg-blue-600 hover:bg-blue-700 text-white py-3.5 rounded-xl font-bold transition shadow-lg hover:shadow-xl disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Split PDF
            </button>
          </form>
        )}
      </div>
    </div>
  );
};

export default ToolSplit;
