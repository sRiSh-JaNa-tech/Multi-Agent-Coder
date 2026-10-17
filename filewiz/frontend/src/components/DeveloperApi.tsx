import React, { useState } from 'react';
import { 
  Key, 
  Code, 
  Copy, 
  Check, 
  ArrowRight, 
  Terminal, 
  ShieldCheck, 
  Zap, 
  Layers, 
  Sparkles, 
  CheckCircle2,
  X
} from 'lucide-react';

interface DeveloperApiProps {
  onNavigate: (view: string) => void;
}

const DeveloperApi: React.FC<DeveloperApiProps> = ({ onNavigate }) => {
  const [copiedIndex, setCopiedIndex] = useState<number | null>(null);
  const [showApplyModal, setShowApplyModal] = useState(false);
  const [appliedKey, setAppliedKey] = useState<string | null>(null);
  const [formData, setFormData] = useState({ name: '', email: '', useCase: 'commercial' });
  const [isSubmitting, setIsSubmitting] = useState(false);

  const copyToClipboard = (text: string, index: number) => {
    navigator.clipboard.writeText(text);
    setCopiedIndex(index);
    setTimeout(() => setCopiedIndex(null), 2000);
  };

  const handleApply = (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setTimeout(() => {
      const generatedKey = `dd_live_${Math.random().toString(36).substring(2, 15)}${Math.random().toString(36).substring(2, 15)}`;
      setAppliedKey(generatedKey);
      setIsSubmitting(false);
    }, 1000);
  };

  const previewApis = [
    {
      id: 1,
      name: 'PDF Conversion Engine',
      endpoint: 'POST /convert/upload',
      description: 'Convert PDF documents to high-resolution PNG, DOCX, or standalone HTML strings.',
      badge: 'POPULAR',
      headers: {
        'Content-Type': 'multipart/form-data',
        'Authorization': 'Bearer dd_live_sample_key_99x'
      },
      requestPayload: `{
  "format": "docx",        // "png" | "docx" | "html"
  "startPage": 1,         // optional page range
  "endPage": 5,
  "file": "<Binary PDF File>"
}`,
      responsePayload: `{
  "success": true,
  "result": {
    "status": "Success",
    "downloadUrl": "/convert/download?fileName=converted-1721568.docx",
    "fileName": "converted-1721568.docx",
    "mode": "DOCX"
  }
}`
    },
    {
      id: 2,
      name: 'Document Compression',
      endpoint: 'POST /compress/pdf/upload',
      description: 'Dramatically shrink PDF file size up to 80% while retaining vector text quality.',
      badge: 'FAST',
      headers: {
        'Content-Type': 'multipart/form-data',
        'Authorization': 'Bearer dd_live_sample_key_99x'
      },
      requestPayload: `{
  "compressionLevel": "recommended", // "low" | "recommended" | "extreme"
  "file": "<Binary PDF File>"
}`,
      responsePayload: `{
  "success": true,
  "originalSize": "14.2 MB",
  "compressedSize": "2.8 MB",
  "ratio": "80.2%",
  "downloadUrl": "/temp/outputs/compressed-pdf-1721590.pdf"
}`
    },
    {
      id: 3,
      name: 'Data Redaction & Sanitization',
      endpoint: 'POST /redaction/process',
      description: 'Scan and permanently redact sensitive PII, SSNs, credit cards, or text bounding boxes.',
      badge: 'SECURE',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer dd_live_sample_key_99x'
      },
      requestPayload: `{
  "fileId": "file_temp_88219",
  "redactions": [
    { "page": 1, "x": 100, "y": 250, "width": 120, "height": 20 },
    { "type": "PII", "pattern": "SSN" }
  ]
}`,
      responsePayload: `{
  "success": true,
  "redactedCount": 2,
  "sanitizedFileUrl": "/temp/outputs/redacted-88219.pdf"
}`
    }
  ];

  return (
    <div className="flex-1 bg-slate-50 min-h-screen pb-24">
      {/* HERO SECTION */}
      <section className="relative pt-24 pb-20 px-6 overflow-hidden flex flex-col items-center justify-center bg-white border-b border-slate-100">
        {/* Ambient Gradients */}
        <div className="absolute top-0 right-1/3 w-[35rem] h-[35rem] bg-gradient-to-tr from-blue-100 to-indigo-200 rounded-full blur-[120px] opacity-60 animate-float-slow pointer-events-none"></div>
        <div className="absolute bottom-0 left-1/3 w-[30rem] h-[30rem] bg-gradient-to-bl from-purple-100 to-pink-100 rounded-full blur-[100px] opacity-50 animate-float-medium pointer-events-none"></div>

        <div className="relative z-10 text-center max-w-4xl mx-auto flex flex-col items-center">
          <div className="mb-4 inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-blue-50 border border-blue-100 text-blue-700 shadow-sm hover:scale-105 transition-transform cursor-default">
            <Sparkles className="w-4 h-4 text-blue-600 animate-pulse" />
            <span className="text-xs font-bold tracking-widest uppercase">FileWiz Developer API v2.0</span>
          </div>

          <h1 className="text-4xl md:text-6xl font-black tracking-tight text-slate-900 mb-6 leading-tight">
            Supercharge your apps with <br className="hidden md:block" />
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-600 via-indigo-600 to-violet-600">
              Powerful Document APIs
            </span>
          </h1>

          <p className="text-slate-600 text-lg md:text-xl max-w-2xl mb-8 font-medium leading-relaxed">
            Integrate enterprise-grade PDF conversion, compression, redaction, and ZIP structure inspection directly into your backend software.
          </p>

          <div className="flex flex-wrap items-center justify-center gap-4">
            <button
              onClick={() => setShowApplyModal(true)}
              className="flex items-center gap-2 px-8 py-4 bg-blue-600 text-white font-bold rounded-2xl shadow-lg shadow-blue-500/25 hover:bg-blue-700 hover:-translate-y-0.5 transition-all"
            >
              <Key className="w-5 h-5" />
              Apply for Developer API Key
            </button>

            <button
              onClick={() => onNavigate('api-directory')}
              className="flex items-center gap-2 px-8 py-4 bg-white text-slate-800 font-bold border border-slate-200 rounded-2xl shadow-sm hover:bg-slate-50 hover:border-slate-300 hover:-translate-y-0.5 transition-all"
            >
              <Terminal className="w-5 h-5 text-indigo-600" />
              Access Full API Directory
              <ArrowRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      </section>

      {/* STATS BANNER */}
      <section className="max-w-7xl mx-auto px-6 -mt-8 relative z-20">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 bg-slate-900 text-white p-6 md:p-8 rounded-3xl shadow-xl border border-slate-800">
          <div className="flex items-center gap-4 p-2">
            <div className="w-12 h-12 rounded-2xl bg-blue-500/20 text-blue-400 flex items-center justify-center">
              <Zap className="w-6 h-6" />
            </div>
            <div>
              <p className="text-2xl font-black">99.99%</p>
              <p className="text-xs text-slate-400 font-medium uppercase tracking-wider">Uptime SLA</p>
            </div>
          </div>
          <div className="flex items-center gap-4 p-2">
            <div className="w-12 h-12 rounded-2xl bg-indigo-500/20 text-indigo-400 flex items-center justify-center">
              <ShieldCheck className="w-6 h-6" />
            </div>
            <div>
              <p className="text-2xl font-black">Zero Logs</p>
              <p className="text-xs text-slate-400 font-medium uppercase tracking-wider">Privacy Guaranteed</p>
            </div>
          </div>
          <div className="flex items-center gap-4 p-2">
            <div className="w-12 h-12 rounded-2xl bg-purple-500/20 text-purple-400 flex items-center justify-center">
              <Layers className="w-6 h-6" />
            </div>
            <div>
              <p className="text-2xl font-black">&lt; 300ms</p>
              <p className="text-xs text-slate-400 font-medium uppercase tracking-wider">Avg Latency</p>
            </div>
          </div>
          <div className="flex items-center gap-4 p-2">
            <div className="w-12 h-12 rounded-2xl bg-emerald-500/20 text-emerald-400 flex items-center justify-center">
              <Code className="w-6 h-6" />
            </div>
            <div>
              <p className="text-2xl font-black">10+ Endpoints</p>
              <p className="text-xs text-slate-400 font-medium uppercase tracking-wider">REST Services</p>
            </div>
          </div>
        </div>
      </section>

      {/* API PREVIEWS SECTION */}
      <section className="max-w-7xl mx-auto px-6 pt-20">
        <div className="flex flex-col md:flex-row md:items-end justify-between mb-12 gap-4">
          <div>
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-md bg-blue-100 text-blue-700 text-xs font-bold uppercase mb-2">
              Sample Schemas
            </div>
            <h2 className="text-3xl font-black text-slate-900">API Endpoint Previews</h2>
            <p className="text-slate-500 mt-1">Explore JSON payload requirements for our core endpoints.</p>
          </div>
          <button
            onClick={() => onNavigate('api-directory')}
            className="inline-flex items-center gap-2 text-blue-600 font-bold hover:text-blue-700 transition"
          >
            Explore Complete Directory
            <ArrowRight className="w-4 h-4" />
          </button>
        </div>

        <div className="space-y-10">
          {previewApis.map((apiItem, idx) => (
            <div 
              key={apiItem.id}
              className="glass-card bg-white rounded-3xl border border-slate-200 shadow-sm overflow-hidden p-6 md:p-8 transition-all hover:border-blue-300 hover:shadow-xl"
            >
              {/* Header */}
              <div className="flex flex-wrap items-center justify-between gap-4 pb-6 border-b border-slate-100">
                <div>
                  <div className="flex items-center gap-3 mb-1">
                    <span className="px-3 py-1 bg-emerald-500 text-white font-bold text-xs rounded-lg uppercase tracking-wider">
                      POST
                    </span>
                    <h3 className="text-xl font-bold text-slate-900">{apiItem.name}</h3>
                    <span className="px-2.5 py-0.5 bg-blue-50 text-blue-600 border border-blue-200 font-bold text-[10px] rounded-full">
                      {apiItem.badge}
                    </span>
                  </div>
                  <p className="text-sm text-slate-500">{apiItem.description}</p>
                </div>
                <div className="font-mono text-sm bg-slate-900 text-slate-200 px-4 py-2 rounded-xl flex items-center gap-3">
                  <span>{apiItem.endpoint}</span>
                  <button 
                    onClick={() => copyToClipboard(apiItem.endpoint, idx * 10)}
                    className="hover:text-blue-400 transition"
                    title="Copy Endpoint"
                  >
                    {copiedIndex === idx * 10 ? <Check className="w-4 h-4 text-emerald-400" /> : <Copy className="w-4 h-4" />}
                  </button>
                </div>
              </div>

              {/* JSON Structures */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mt-6">
                {/* Request Payload */}
                <div className="bg-slate-950 rounded-2xl p-5 border border-slate-800 text-slate-200 flex flex-col justify-between">
                  <div>
                    <div className="flex items-center justify-between mb-3 pb-2 border-b border-slate-800">
                      <span className="text-xs font-bold text-slate-400 uppercase tracking-wider">Request JSON Payload</span>
                      <button 
                        onClick={() => copyToClipboard(apiItem.requestPayload, idx * 10 + 1)}
                        className="text-xs text-slate-400 hover:text-white flex items-center gap-1 transition"
                      >
                        {copiedIndex === idx * 10 + 1 ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                        {copiedIndex === idx * 10 + 1 ? 'Copied' : 'Copy'}
                      </button>
                    </div>
                    <pre className="font-mono text-xs text-blue-300 overflow-x-auto p-1 leading-relaxed">
                      {apiItem.requestPayload}
                    </pre>
                  </div>
                </div>

                {/* Response Payload */}
                <div className="bg-slate-950 rounded-2xl p-5 border border-slate-800 text-slate-200 flex flex-col justify-between">
                  <div>
                    <div className="flex items-center justify-between mb-3 pb-2 border-b border-slate-800">
                      <span className="text-xs font-bold text-slate-400 uppercase tracking-wider">Response JSON Structure (200 OK)</span>
                      <button 
                        onClick={() => copyToClipboard(apiItem.responsePayload, idx * 10 + 2)}
                        className="text-xs text-slate-400 hover:text-white flex items-center gap-1 transition"
                      >
                        {copiedIndex === idx * 10 + 2 ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                        {copiedIndex === idx * 10 + 2 ? 'Copied' : 'Copy'}
                      </button>
                    </div>
                    <pre className="font-mono text-xs text-emerald-400 overflow-x-auto p-1 leading-relaxed">
                      {apiItem.responsePayload}
                    </pre>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* BOTTOM BANNER TO ACCESS FULL API DIRECTORY */}
      <section className="max-w-7xl mx-auto px-6 mt-16">
        <div className="ad-banner rounded-3xl p-8 md:p-12 flex flex-col md:flex-row items-center justify-between gap-8 shadow-2xl">
          <div className="ad-shine"></div>
          <div className="z-10 max-w-xl text-center md:text-left">
            <span className="px-3 py-1 bg-indigo-500 text-white font-bold text-xs rounded-full uppercase tracking-wider mb-4 inline-block">
              Full API Specification
            </span>
            <h2 className="text-3xl md:text-4xl font-black text-white mb-3">
              Need all 10+ endpoints with full JSON formats?
            </h2>
            <p className="text-slate-300 text-base md:text-lg mb-6 leading-relaxed">
              Explore our comprehensive API Directory featuring cURL examples, parameter types, error response structures, and interactive documentation.
            </p>
            <button
              onClick={() => onNavigate('api-directory')}
              className="inline-flex items-center gap-2 bg-blue-600 hover:bg-blue-500 text-white px-8 py-4 rounded-2xl font-bold text-lg transition-all shadow-xl shadow-blue-600/30 hover:-translate-y-1"
            >
              Access Full API Directory
              <ArrowRight className="w-5 h-5" />
            </button>
          </div>
          <div className="z-10 relative flex justify-center items-center">
          <div className="rounded-3xl overflow-hidden">
            <img
              src="/assets/api.gif"
              alt="Interactive Directory & JSON Schemas"
              className="w-72 md:w-96 lg:w-[420px] h-auto max-h-80 object-contain"
            />
          </div>
        </div>
        </div>
      </section>

      {/* APPLY FOR DEVELOPER API MODAL */}
      {showApplyModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="bg-white rounded-3xl max-w-lg w-full p-8 shadow-2xl border border-slate-100 relative animate-in zoom-in-95 duration-200">
            <button 
              onClick={() => { setShowApplyModal(false); setAppliedKey(null); }}
              className="absolute top-6 right-6 text-slate-400 hover:text-slate-600 p-1 rounded-full hover:bg-slate-100 transition"
            >
              <X className="w-5 h-5" />
            </button>

            {!appliedKey ? (
              <>
                <div className="flex items-center gap-3 mb-6">
                  <div className="w-12 h-12 bg-blue-50 border border-blue-100 text-blue-600 rounded-2xl flex items-center justify-center">
                    <Key className="w-6 h-6" />
                  </div>
                  <div>
                    <h3 className="text-xl font-bold text-slate-900">Apply for Developer Access</h3>
                    <p className="text-xs text-slate-500">Get your API key with 10,000 free monthly requests</p>
                  </div>
                </div>

                <form onSubmit={handleApply} className="space-y-4">
                  <div>
                    <label className="block text-xs font-bold uppercase text-slate-500 mb-1">Developer / Organization Name</label>
                    <input 
                      type="text" 
                      required
                      placeholder="e.g. Acme Corp or Jane Doe"
                      value={formData.name}
                      onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                      className="w-full px-4 py-3 rounded-xl border border-slate-200 focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm font-medium"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-bold uppercase text-slate-500 mb-1">Work Email</label>
                    <input 
                      type="email" 
                      required
                      placeholder="dev@yourcompany.com"
                      value={formData.email}
                      onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                      className="w-full px-4 py-3 rounded-xl border border-slate-200 focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm font-medium"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-bold uppercase text-slate-500 mb-1">Intended Use Case</label>
                    <select 
                      value={formData.useCase}
                      onChange={(e) => setFormData({ ...formData, useCase: e.target.value })}
                      className="w-full px-4 py-3 rounded-xl border border-slate-200 focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm font-medium bg-white"
                    >
                      <option value="commercial">Commercial Application</option>
                      <option value="personal">Personal / Side Project</option>
                      <option value="education">Academic / Research</option>
                    </select>
                  </div>

                  <div className="pt-4">
                    <button
                      type="submit"
                      disabled={isSubmitting}
                      className="w-full py-4 bg-blue-600 text-white font-bold rounded-2xl hover:bg-blue-700 transition shadow-lg shadow-blue-500/25 flex items-center justify-center gap-2"
                    >
                      {isSubmitting ? (
                        <>
                          <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                          <span>Generating Credentials...</span>
                        </>
                      ) : (
                        <>
                          <span>Submit &amp; Generate API Key</span>
                          <ArrowRight className="w-4 h-4" />
                        </>
                      )}
                    </button>
                  </div>
                </form>
              </>
            ) : (
              <div className="text-center py-4">
                <div className="w-16 h-16 bg-emerald-100 text-emerald-600 rounded-full flex items-center justify-center mx-auto mb-4">
                  <CheckCircle2 className="w-10 h-10" />
                </div>
                <h3 className="text-2xl font-black text-slate-900 mb-2">API Key Generated!</h3>
                <p className="text-slate-600 text-sm mb-6">
                  Welcome aboard, <span className="font-semibold text-slate-800">{formData.name}</span>. Your developer account is ready.
                </p>

                <div className="bg-slate-950 p-4 rounded-2xl border border-slate-800 mb-6 text-left relative">
                  <span className="text-[10px] font-bold text-slate-400 uppercase tracking-widest block mb-1">Your Live API Key</span>
                  <p className="font-mono text-emerald-400 text-xs break-all pr-8">{appliedKey}</p>
                  <button
                    onClick={() => copyToClipboard(appliedKey, 999)}
                    className="absolute top-4 right-4 text-slate-400 hover:text-white"
                  >
                    {copiedIndex === 999 ? <Check className="w-4 h-4 text-emerald-400" /> : <Copy className="w-4 h-4" />}
                  </button>
                </div>

                <div className="flex gap-3">
                  <button
                    onClick={() => { setShowApplyModal(false); setAppliedKey(null); onNavigate('api-directory'); }}
                    className="flex-1 py-3 bg-blue-600 text-white font-bold rounded-xl hover:bg-blue-700 transition text-sm"
                  >
                    View API Directory
                  </button>
                  <button
                    onClick={() => { setShowApplyModal(false); setAppliedKey(null); }}
                    className="px-6 py-3 border border-slate-200 text-slate-700 font-bold rounded-xl hover:bg-slate-50 transition text-sm"
                  >
                    Done
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default DeveloperApi;
