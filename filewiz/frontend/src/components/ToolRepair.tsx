import React, { useState } from 'react';
import { Upload, FileText, CheckCircle2, AlertCircle, Wrench } from 'lucide-react';
import api from '../utils/api';

interface RepairResult {
  fileName: string;
  fileSize: number;
  pages: number;
  corruptionType: string;
  repairMethod: string;
  status: string;
  confidence: number;
  downloadUrl: string | null;
}

const ToolRepair: React.FC = () => {
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<RepairResult | null>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      setFile(e.target.files[0]);
      setError(null);
      setResult(null);
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
      setResult(null);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) {
      setError('Please select a file.');
      return;
    }

    setError(null);
    setLoading(true);

    const formData = new FormData();
    formData.append('pdf', file);

    try {
      const response = await api.post('/repair/upload', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });

      if (response.data.success) {
        setResult(response.data.result);
        if (!response.data.result.downloadUrl) {
          setError('PDF could not be recovered by standard methods.');
        }
      } else {
        throw new Error('Repair failed');
      }
    } catch (err: any) {
      console.error('Repair error:', err);
      setError(err.response?.data?.error || 'An unexpected error occurred during PDF repair.');
    } finally {
      setLoading(false);
    }
  };

  const resetTool = () => {
    setFile(null);
    setResult(null);
    setError(null);
  };

  return (
    <div className="flex-1 flex items-center justify-center py-12 px-4 bg-slate-50">
      <div className="w-full max-w-xl bg-white rounded-3xl shadow-xl p-8 border border-slate-100">
        <h2 className="text-3xl font-black text-center text-slate-800">
          Repair PDF Structure
        </h2>
        <p className="text-center text-slate-500 mt-2 text-sm">
          Detect corruption and rebuild broken cross-reference tables
        </p>

        {error && !result && (
          <div className="mt-6 flex items-center gap-2 bg-rose-50 border border-rose-200 text-rose-600 px-4 py-3 rounded-xl text-center text-sm font-medium">
            <AlertCircle className="w-5 h-5 flex-shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {loading ? (
          <div className="text-center py-12 space-y-4">
            <div className="relative w-16 h-16 mx-auto">
              <div className="animate-spin rounded-full h-16 w-16 border-t-2 border-b-2 border-blue-600"></div>
              <Wrench className="w-6 h-6 text-blue-600 absolute inset-0 m-auto animate-pulse" />
            </div>
            <p className="text-blue-700 font-bold animate-pulse text-sm">
              Analyzing file syntax and rebuilding header tables...
            </p>
          </div>
        ) : result ? (
          <div className="mt-8 space-y-6">
            <div className="bg-slate-50 border border-slate-200 rounded-2xl p-6 space-y-4">
              <h3 className="text-sm font-bold text-slate-700 uppercase tracking-wider text-center border-b border-slate-200 pb-2">
                Diagnostic Report
              </h3>
              
              <div className="grid grid-cols-2 gap-4 text-xs font-semibold text-slate-600">
                <div>File Name</div>
                <div className="text-right text-slate-800">{result.fileName}</div>

                <div>File Size</div>
                <div className="text-right text-slate-800">{result.fileSize} KB</div>

                <div>Page Count</div>
                <div className="text-right text-slate-800">{result.pages}</div>

                <div>Corruption Class</div>
                <div className="text-right text-rose-500">{result.corruptionType}</div>

                <div>Rebuild Pipeline</div>
                <div className="text-right text-blue-600">{result.repairMethod}</div>

                <div>Status</div>
                <div className={`text-right ${result.downloadUrl ? 'text-green-600' : 'text-rose-600'}`}>
                  {result.status}
                </div>

                <div>Confidence</div>
                <div className="text-right text-slate-800">{(result.confidence * 100).toFixed(0)}%</div>
              </div>
            </div>

            {result.downloadUrl ? (
              <div className="bg-green-50 border border-green-200 text-green-700 p-6 rounded-2xl text-center">
                <CheckCircle2 className="w-8 h-8 text-green-500 mx-auto mb-2" />
                <p className="font-bold text-lg mb-1">Repair successful! 🎉</p>
                <p className="text-xs text-green-600/80 mb-4 font-medium">Click download to retrieve your repaired file.</p>
                <a
                  href={`http://localhost:3000${result.downloadUrl}`}
                  className="block w-full text-center bg-green-600 hover:bg-green-700 text-white py-3.5 rounded-xl font-bold transition shadow-lg hover:shadow-xl"
                >
                  Download Repaired PDF
                </a>
              </div>
            ) : (
              <div className="bg-rose-50 border border-rose-200 text-rose-700 p-6 rounded-2xl text-center text-sm font-medium">
                We were unable to repair this specific PDF structural damage.
              </div>
            )}

            <button
              onClick={resetTool}
              className="block w-full text-center text-sm font-bold text-slate-400 hover:text-slate-600 uppercase tracking-widest"
            >
              Analyze another file
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
                        Drag & drop your corrupted PDF here
                      </p>
                      <p className="text-xs text-slate-400 mt-1">
                        or click to browse files
                      </p>
                    </>
                  )}
                </div>
              </label>
            </div>

            <button
              type="submit"
              disabled={!file}
              className="w-full bg-blue-600 hover:bg-blue-700 text-white py-3.5 rounded-xl font-bold transition shadow-lg hover:shadow-xl disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Start Repair Process
            </button>
          </form>
        )}
      </div>
    </div>
  );
};

export default ToolRepair;
