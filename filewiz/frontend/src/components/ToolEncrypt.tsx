import React, { useState } from 'react';
import { Upload, FileText, Lock, CheckCircle2, AlertCircle } from 'lucide-react';
import api from '../utils/api';

const ToolEncrypt: React.FC = () => {
  const [file, setFile] = useState<File | null>(null);
  const [userPassword, setUserPassword] = useState('');
  const [ownerPassword, setOwnerPassword] = useState('');
  const [encryptionLevel, setEncryptionLevel] = useState('128');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
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
      setError('Please select a file.');
      return;
    }
    if (!userPassword) {
      setError('Please enter a user password.');
      return;
    }

    setError(null);
    setLoading(true);

    const formData = new FormData();
    formData.append('pdf', file);
    formData.append('user_password', userPassword);
    formData.append('owner_password', ownerPassword || userPassword);
    formData.append('encryption_level', encryptionLevel);

    try {
      const response = await api.post('/encrypt/upload', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });

      if (response.data.success) {
        setDownloadLink(response.data.downloadLink);
      } else {
        throw new Error('Encryption failed');
      }
    } catch (err: any) {
      console.error('Encryption error:', err);
      setError(err.response?.data?.error || 'PDF encryption failed. Ensure the PDF is not already protected.');
      setLoading(false);
    }
  };

  const resetTool = () => {
    setFile(null);
    setUserPassword('');
    setOwnerPassword('');
    setDownloadLink(null);
    setLoading(false);
  };

  return (
    <div className="flex-1 flex items-center justify-center py-12 px-4 bg-slate-50">
      <div className="w-full max-w-xl bg-white rounded-3xl shadow-xl p-8 border border-slate-100">
        <h2 className="text-3xl font-black text-center text-slate-800">
          Encrypt PDF
        </h2>
        <p className="text-center text-slate-500 mt-2 text-sm">
          Protect your documents with standard password encryption
        </p>

        {error && (
          <div className="mt-6 flex items-center gap-2 bg-rose-50 border border-rose-200 text-rose-600 px-4 py-3 rounded-xl text-center text-sm font-medium">
            <AlertCircle className="w-5 h-5 flex-shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {loading ? (
          <div className="mt-8 space-y-6">
            {downloadLink ? (
              <div className="space-y-6">
                {/* Download Area */}
                <div className="bg-green-50 border border-green-200 text-green-700 p-6 rounded-2xl text-center">
                  <CheckCircle2 className="w-8 h-8 text-green-500 mx-auto mb-2" />
                  <p className="font-bold text-lg mb-1">Encryption successful! 🎉</p>
                  <p className="text-xs text-green-600/80 mb-4">Your PDF has been locked with the password.</p>
                  <a
                    href={`http://localhost:3000${downloadLink}`}
                    className="block w-full text-center bg-green-600 hover:bg-green-700 text-white py-3.5 rounded-xl font-bold transition shadow-lg hover:shadow-xl"
                  >
                    Download Encrypted PDF
                  </a>
                </div>

                <button
                  onClick={resetTool}
                  className="block w-full text-center text-sm font-bold text-slate-400 hover:text-slate-600 mt-4 uppercase tracking-widest"
                >
                  Encrypt another file
                </button>
              </div>
            ) : (
              <div className="text-center py-6">
                <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-blue-600 mx-auto mb-4"></div>
                <p className="text-blue-700 font-bold animate-pulse text-sm">
                  Encrypting PDF and sealing structure...
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

            {/* Passwords */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-bold text-slate-400 uppercase tracking-widest mb-2">
                  User Password
                </label>
                <div className="relative">
                  <input
                    type="password"
                    required
                    value={userPassword}
                    onChange={(e) => setUserPassword(e.target.value)}
                    placeholder="Require password to view"
                    className="w-full pl-10 pr-4 py-3 border border-slate-200 rounded-xl focus:ring-2 focus:ring-blue-500 focus:outline-none transition-all text-sm"
                  />
                  <Lock className="w-4 h-4 text-slate-400 absolute left-3.5 top-3.5" />
                </div>
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-400 uppercase tracking-widest mb-2">
                  Owner Password (Optional)
                </label>
                <div className="relative">
                  <input
                    type="password"
                    value={ownerPassword}
                    onChange={(e) => setOwnerPassword(e.target.value)}
                    placeholder="Require password to edit"
                    className="w-full pl-10 pr-4 py-3 border border-slate-200 rounded-xl focus:ring-2 focus:ring-blue-500 focus:outline-none transition-all text-sm"
                  />
                  <Lock className="w-4 h-4 text-slate-400 absolute left-3.5 top-3.5" />
                </div>
              </div>
            </div>

            {/* Encryption Level */}
            <div>
              <label htmlFor="encryptionLevel" className="block text-xs font-bold text-slate-400 uppercase tracking-widest mb-2">
                Encryption Bit Rate
              </label>
              <select
                id="encryptionLevel"
                value={encryptionLevel}
                onChange={(e) => setEncryptionLevel(e.target.value)}
                className="w-full border border-slate-200 rounded-xl px-4 py-3 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm font-medium"
              >
                <option value="128">128-bit AES Encryption (Recommended)</option>
                <option value="256">256-bit AES Encryption (Highest)</option>
                <option value="40">40-bit RC4 Encryption (Legacy)</option>
              </select>
            </div>

            <button
              type="submit"
              disabled={!file || !userPassword}
              className="w-full bg-blue-600 hover:bg-blue-700 text-white py-3.5 rounded-xl font-bold transition shadow-lg hover:shadow-xl disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Encrypt PDF
            </button>
          </form>
        )}
      </div>
    </div>
  );
};

export default ToolEncrypt;
