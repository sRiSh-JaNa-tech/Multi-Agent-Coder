import React, { useState } from 'react';
import { Upload, FileText, CheckCircle2, AlertCircle } from 'lucide-react';
import api from '../utils/api';

const ToolCompressPpt: React.FC = () => {
  const [file, setFile] = useState<File | null>(null);
  const [compressionLevel, setCompressionLevel] = useState('normal');
  const [removeMedia, setRemoveMedia] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [stats, setStats] = useState<{ before: string; after: string; reduction: string } | null>(null);
  const [downloadLink, setDownloadLink] = useState<string | null>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      setFile(e.target.files[0]);
      setError(null);
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
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) {
      setError('Please select a PowerPoint file.');
      return;
    }

    setError(null);
    setLoading(true);
    setProgress(0);

    const formData = new FormData();
    formData.append('ppt', file);
    formData.append('compressionLevel', compressionLevel);
    if (removeMedia) {
      formData.append('removeMedia', 'on');
    }

    // Simulate progress
    const progressInterval = setInterval(() => {
      setProgress((prev) => {
        if (prev >= 90) {
          clearInterval(progressInterval);
          return 90;
        }
        return prev + 5;
      });
    }, 100);

    try {
      const response = await api.post('/compress/ppt/result', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });

      clearInterval(progressInterval);
      setProgress(100);

      if (response.data.success) {
        setStats(response.data.stats);
        setDownloadLink(response.data.downloadLink);
      } else {
        throw new Error('PPT Compression failed');
      }
    } catch (err: any) {
      clearInterval(progressInterval);
      console.error('PPT Compression error:', err);
      setError(err.response?.data?.error || 'PowerPoint compression failed. Please check inputs.');
      setLoading(false);
    }
  };

  const resetTool = () => {
    setFile(null);
    setStats(null);
    setDownloadLink(null);
    setProgress(0);
    setLoading(false);
  };

  return (
    <div className="flex-1 flex items-center justify-center py-12 px-4 bg-slate-50">
      <div className="w-full max-w-xl bg-white rounded-3xl shadow-xl p-8 border border-slate-100">
        <h2 className="text-3xl font-black text-center text-slate-800">
          Shrink Slides (PPT)
        </h2>
        <p className="text-center text-slate-500 mt-2 text-sm">
          Optimize PowerPoint files for smaller storage size
        </p>

        {error && (
          <div className="mt-6 flex items-center gap-2 bg-rose-50 border border-rose-200 text-rose-600 px-4 py-3 rounded-xl text-center text-sm font-medium">
            <AlertCircle className="w-5 h-5 flex-shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {loading ? (
          <div className="mt-8 space-y-6">
            {stats && downloadLink && progress === 100 ? (
              <div className="space-y-6">
                {/* Stats */}
                <div className="bg-blue-50 border border-blue-200 rounded-2xl p-6">
                  <h3 className="text-blue-800 font-bold mb-4 text-center text-sm uppercase tracking-wider">Compression Results</h3>
                  <div className="grid grid-cols-3 gap-4 text-center">
                    <div>
                      <p className="text-xs text-slate-400 font-bold uppercase">Original</p>
                      <p className="font-extrabold text-slate-700 mt-1">{stats.before}</p>
                    </div>
                    <div>
                      <p className="text-xs text-slate-400 font-bold uppercase">Compressed</p>
                      <p className="font-extrabold text-green-600 mt-1">{stats.after}</p>
                    </div>
                    <div>
                      <p className="text-xs text-slate-400 font-bold uppercase">Reduction</p>
                      <p className="font-extrabold text-blue-600 mt-1">{stats.reduction}</p>
                    </div>
                  </div>
                </div>

                {/* Download Area */}
                <div className="bg-green-50 border border-green-200 text-green-700 p-6 rounded-2xl text-center">
                  <CheckCircle2 className="w-8 h-8 text-green-500 mx-auto mb-2" />
                  <p className="font-bold text-lg mb-1">Compression successful! 🎉</p>
                  <p className="text-xs text-green-600/80 mb-4">Your PowerPoint file has been optimized.</p>
                  <a
                    href={`http://localhost:3000${downloadLink}`}
                    download="compressed_presentation.pptx"
                    className="block w-full text-center bg-green-600 hover:bg-green-700 text-white py-3.5 rounded-xl font-bold transition shadow-lg hover:shadow-xl"
                  >
                    Download Presentation
                  </a>
                </div>

                <button
                  onClick={resetTool}
                  className="block w-full text-center text-sm font-bold text-slate-400 hover:text-slate-600 mt-4 uppercase tracking-widest"
                >
                  Compress another file
                </button>
              </div>
            ) : (
              <div className="text-center py-6">
                <div className="w-full bg-slate-100 rounded-full h-3 mb-4 overflow-hidden">
                  <div
                    className="bg-blue-600 h-3 rounded-full transition-all duration-300"
                    style={{ width: `${progress}%` }}
                  ></div>
                </div>
                <p className="text-blue-700 font-bold animate-pulse text-sm">
                  {progress < 90 ? 'Uploading and compressing slides...' : 'Saving slides...'}
                </p>
              </div>
            )}
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
                id="ppt-file"
                type="file"
                accept=".ppt,.pptx"
                className="hidden"
                onChange={handleFileChange}
              />
              <label htmlFor="ppt-file" className="flex flex-col items-center justify-center w-full h-full cursor-pointer">
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
                        Drag & drop your presentation here
                      </p>
                      <p className="text-xs text-slate-400 mt-1">
                        or click to browse files (.ppt, .pptx)
                      </p>
                    </>
                  )}
                </div>
              </label>
            </div>

            {/* Compression Options */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label htmlFor="compressionLevel" className="block text-xs font-bold text-slate-400 uppercase tracking-widest mb-2">
                  Compression Level
                </label>
                <select
                  id="compressionLevel"
                  value={compressionLevel}
                  onChange={(e) => setCompressionLevel(e.target.value)}
                  className="w-full border border-slate-200 rounded-xl px-4 py-3 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm font-medium"
                >
                  <option value="normal">Normal Compression</option>
                  <option value="low">Low (Fastest)</option>
                  <option value="extreme">Extreme (Smallest)</option>
                </select>
              </div>

              <div className="flex items-center mt-6">
                <label className="flex items-center space-x-2.5 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={removeMedia}
                    onChange={(e) => setRemoveMedia(e.target.checked)}
                    className="w-4.5 h-4.5 rounded text-blue-600 border-slate-300 focus:ring-blue-500 transition cursor-pointer"
                  />
                  <div className="flex flex-col">
                    <span className="text-sm font-semibold text-slate-700">Strip Media / Audio</span>
                    <span className="text-[10px] text-slate-400">Removes heavy audio/video streams</span>
                  </div>
                </label>
              </div>
            </div>

            <button
              type="submit"
              disabled={!file}
              className="w-full bg-blue-600 hover:bg-blue-700 text-white py-3.5 rounded-xl font-bold transition shadow-lg hover:shadow-xl disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Compress PPT
            </button>
          </form>
        )}
      </div>
    </div>
  );
};

export default ToolCompressPpt;
