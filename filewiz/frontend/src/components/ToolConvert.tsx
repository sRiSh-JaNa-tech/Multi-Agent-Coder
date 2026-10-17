import React, { useState } from 'react';
import { Upload, FileText, CheckCircle2, AlertCircle, FileType } from 'lucide-react';
import api from '../utils/api';

const ToolConvert: React.FC = () => {
  const [file, setFile] = useState<File | null>(null);
  const [format, setFormat] = useState('png');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<{ downloadUrl: string; fileName: string; mode: string } | null>(null);

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
    formData.append('format', format);

    try {
      const response = await api.post('/convert/upload', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });

      if (response.data.success) {
        setResult(response.data.result);
      } else {
        throw new Error('Conversion failed');
      }
    } catch (err: any) {
      console.error('Conversion error:', err);
      setError(err.response?.data?.error || 'Format conversion failed. Please check files.');
    } finally {
      setLoading(false);
    }
  };

  const resetTool = () => {
    setFile(null);
    setResult(null);
    setError(null);
  };

  const formats = [
    { value: 'png', label: 'PNG', category: 'Image' },
    { value: 'jpeg', label: 'JPEG', category: 'Image' },
    { value: 'html', label: 'HTML', category: 'Web' },
    { value: 'docx', label: 'DOCX', category: 'Document' },
  ];

  return (
    <div className="flex-1 flex items-center justify-center py-12 px-4 bg-slate-50">
      <div className="w-full max-w-xl bg-white rounded-3xl shadow-xl p-8 border border-slate-100">
        <h2 className="text-3xl font-black text-center text-slate-800">
          Convert Format
        </h2>
        <p className="text-center text-slate-500 mt-2 text-sm">
          Transform your PDF into images, HTML, or DOCX formats
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
              <FileType className="w-6 h-6 text-blue-600 absolute inset-0 m-auto animate-pulse" />
            </div>
            <p className="text-blue-700 font-bold animate-pulse text-sm">
              Rendering layout vectors and translating document markup...
            </p>
          </div>
        ) : result ? (
          <div className="mt-8 space-y-6">
            {/* Download Area */}
            <div className="bg-green-50 border border-green-200 text-green-700 p-6 rounded-2xl text-center">
              <CheckCircle2 className="w-8 h-8 text-green-500 mx-auto mb-2" />
              <p className="font-bold text-lg mb-1">Conversion successful! 🎉</p>
              <p className="text-xs text-green-600/80 mb-4 font-semibold">Your file has been transformed to {result.mode}.</p>
              <a
                href={`http://localhost:3000${result.downloadUrl}`}
                className="block w-full text-center bg-green-600 hover:bg-green-700 text-white py-3.5 rounded-xl font-bold transition shadow-lg hover:shadow-xl"
              >
                Download Converted File
              </a>
            </div>

            <button
              onClick={resetTool}
              className="block w-full text-center text-sm font-bold text-slate-400 hover:text-slate-600 uppercase tracking-widest"
            >
              Convert another file
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

            {/* Format Selection Grid */}
            <div>
              <label className="block text-xs font-bold text-slate-400 uppercase tracking-widest mb-3">
                Choose Output Format
              </label>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                {formats.map((fmt) => (
                  <label key={fmt.value} className="cursor-pointer">
                    <input
                      type="radio"
                      name="format"
                      value={fmt.value}
                      checked={format === fmt.value}
                      onChange={() => setFormat(fmt.value)}
                      className="hidden"
                    />
                    <div
                      className={`border-2 rounded-2xl p-4 text-center transition-all ${
                        format === fmt.value
                          ? 'border-blue-500 bg-blue-50/50 text-blue-700'
                          : 'border-slate-100 hover:border-blue-200 text-slate-600 bg-white'
                      }`}
                    >
                      <div className="font-black text-lg mb-0.5">{fmt.label}</div>
                      <div className="text-[10px] text-slate-400 font-bold uppercase">{fmt.category}</div>
                    </div>
                  </label>
                ))}
              </div>
            </div>

            <button
              type="submit"
              disabled={!file}
              className="w-full bg-blue-600 hover:bg-blue-700 text-white py-3.5 rounded-xl font-bold transition shadow-lg hover:shadow-xl disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Convert PDF
            </button>
          </form>
        )}
      </div>
    </div>
  );
};

export default ToolConvert;
