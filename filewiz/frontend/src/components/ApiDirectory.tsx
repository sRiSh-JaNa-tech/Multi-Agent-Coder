import React, { useState } from 'react';
import { 
  Terminal, 
  Search, 
  Copy, 
  Check, 
  ArrowLeft, 
  FileText, 
  Lock, 
  ShieldCheck, 
  Archive, 
  Layers, 
  Zap, 
  Key, 
  Code2
} from 'lucide-react';

interface ApiDirectoryProps {
  onNavigate: (view: string) => void;
}

interface ApiEndpoint {
  id: string;
  category: 'pdf' | 'ppt' | 'security' | 'archive' | 'auth';
  method: 'POST' | 'GET';
  path: string;
  title: string;
  description: string;
  authRequired: boolean;
  headers: Record<string, string>;
  requestJson: string;
  responseJson200: string;
  responseJson400: string;
  curlSnippet: string;
  jsSnippet: string;
  pythonSnippet: string;
}

const ApiDirectory: React.FC<ApiDirectoryProps> = ({ onNavigate }) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<string>('all');
  const [activeCodeTabs, setActiveCodeTabs] = useState<Record<string, 'curl' | 'js' | 'python'>>({});
  const [copiedKey, setCopiedKey] = useState<string | null>(null);

  const copyText = (text: string, id: string) => {
    navigator.clipboard.writeText(text);
    setCopiedKey(id);
    setTimeout(() => setCopiedKey(null), 2000);
  };

  const setCodeTab = (endpointId: string, tab: 'curl' | 'js' | 'python') => {
    setActiveCodeTabs(prev => ({ ...prev, [endpointId]: tab }));
  };

  const endpoints: ApiEndpoint[] = [
    {
      id: 'convert-upload',
      category: 'pdf',
      method: 'POST',
      path: '/convert/upload',
      title: 'Convert PDF Format',
      description: 'Converts a PDF file into high-res PNG images, Microsoft Word (.docx), or HTML file.',
      authRequired: false,
      headers: {
        'Content-Type': 'multipart/form-data'
      },
      requestJson: `{
  "format": "docx", // "png" | "docx" | "html"
  "startPage": 1,   // optional integer page start
  "endPage": 5,     // optional integer page end
  "pdf": "<File binary stream>"
}`,
      responseJson200: `{
  "success": true,
  "result": {
    "status": "Success",
    "downloadUrl": "/convert/download?fileName=converted-17215918.docx",
    "fileName": "converted-17215918.docx",
    "mode": "DOCX"
  }
}`,
      responseJson400: `{
  "error": "Only PDF files allowed"
}`,
      curlSnippet: `curl -X POST "http://localhost:3000/convert/upload" \\
  -F "format=docx" \\
  -F "startPage=1" \\
  -F "endPage=5" \\
  -F "pdf=@/path/to/document.pdf"`,
      jsSnippet: `const formData = new FormData();
formData.append('format', 'docx');
formData.append('pdf', fileInput.files[0]);

const response = await fetch('http://localhost:3000/convert/upload', {
  method: 'POST',
  body: formData
});
const data = await response.json();`,
      pythonSnippet: `import requests

url = "http://localhost:3000/convert/upload"
files = {'pdf': open('document.pdf', 'rb')}
data = {'format': 'docx', 'startPage': 1, 'endPage': 5}

response = requests.post(url, files=files, data=data)
print(response.json())`
    },
    {
      id: 'compress-pdf',
      category: 'pdf',
      method: 'POST',
      path: '/compress/pdf/upload',
      title: 'Compress PDF File',
      description: 'Optimizes font tables, strips unneeded metadata, and downsamples images inside a PDF.',
      authRequired: true,
      headers: {
        'Content-Type': 'multipart/form-data',
        'Cookie': 'filewiz-session=...'
      },
      requestJson: `{
  "compressionLevel": "recommended", // "low" | "recommended" | "extreme"
  "pdf": "<File binary stream>"
}`,
      responseJson200: `{
  "success": true,
  "originalSize": "12.4 MB",
  "compressedSize": "2.1 MB",
  "downloadUrl": "/temp/outputs/compressed-pdf-17215920.pdf"
}`,
      responseJson400: `{
  "error": "Usage limit reached. Please log in or sign up to continue."
}`,
      curlSnippet: `curl -X POST "http://localhost:3000/compress/pdf/upload" \\
  -F "compressionLevel=recommended" \\
  -F "pdf=@/path/to/document.pdf"`,
      jsSnippet: `const formData = new FormData();
formData.append('pdf', pdfFile);

const res = await fetch('http://localhost:3000/compress/pdf/upload', {
  method: 'POST',
  body: formData
});
const result = await res.json();`,
      pythonSnippet: `import requests

files = {'pdf': open('document.pdf', 'rb')}
res = requests.post('http://localhost:3000/compress/pdf/upload', files=files)
print(res.json())`
    },
    {
      id: 'compress-ppt',
      category: 'ppt',
      method: 'POST',
      path: '/compress/ppt/upload',
      title: 'Compress PowerPoint (.pptx)',
      description: 'Compresses images and media embeds inside Microsoft PowerPoint presentations.',
      authRequired: false,
      headers: {
        'Content-Type': 'multipart/form-data'
      },
      requestJson: `{
  "ppt": "<File binary .pptx stream>"
}`,
      responseJson200: `{
  "success": true,
  "originalSize": "45.0 MB",
  "compressedSize": "8.2 MB",
  "downloadUrl": "/temp/outputs/compressed-ppt-17215922.pptx"
}`,
      responseJson400: `{
  "error": "Only PowerPoint (.pptx) files allowed"
}`,
      curlSnippet: `curl -X POST "http://localhost:3000/compress/ppt/upload" \\
  -F "ppt=@/path/to/presentation.pptx"`,
      jsSnippet: `const formData = new FormData();
formData.append('ppt', pptxFile);

const res = await fetch('http://localhost:3000/compress/ppt/upload', {
  method: 'POST',
  body: formData
});`,
      pythonSnippet: `import requests

files = {'ppt': open('presentation.pptx', 'rb')}
res = requests.post('http://localhost:3000/compress/ppt/upload', files=files)
print(res.json())`
    },
    {
      id: 'redaction-process',
      category: 'security',
      method: 'POST',
      path: '/redaction',
      title: 'Sanitize & Redact PDF',
      description: 'Permanently burns out sensitive text coordinates or automatically redacts PII patterns.',
      authRequired: true,
      headers: {
        'Content-Type': 'application/json'
      },
      requestJson: `{
  "fileId": "ws_172159_9921",
  "page": 1,
  "boxes": [
    { "x": 100, "y": 200, "w": 150, "h": 25 }
  ]
}`,
      responseJson200: `{
  "success": true,
  "sanitizedPdfUrl": "/temp/outputs/redacted-172159.pdf"
}`,
      responseJson400: `{
  "error": "Usage limit reached. Please log in or sign up to continue."
}`,
      curlSnippet: `curl -X POST "http://localhost:3000/redaction" \\
  -H "Content-Type: application/json" \\
  -d '{"fileId":"ws_172159_9921","page":1,"boxes":[{"x":100,"y":200,"w":150,"h":25}]}'`,
      jsSnippet: `const res = await fetch('http://localhost:3000/redaction', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ fileId: 'ws_172159_9921', page: 1, boxes: [{ x: 100, y: 200, w: 150, h: 25 }] })
});`,
      pythonSnippet: `import requests

payload = {"fileId": "ws_172159_9921", "page": 1, "boxes": [{"x": 100, "y": 200, "w": 150, "h": 25}]}
res = requests.post('http://localhost:3000/redaction', json=payload)
print(res.json())`
    },
    {
      id: 'encrypt-pdf',
      category: 'security',
      method: 'POST',
      path: '/encrypt',
      title: 'AES Encrypt PDF',
      description: 'Locks a PDF document with password encryption and user permission flags.',
      authRequired: true,
      headers: {
        'Content-Type': 'multipart/form-data'
      },
      requestJson: `{
  "password": "SuperSecretPassword123",
  "pdf": "<Binary PDF Stream>"
}`,
      responseJson200: `{
  "success": true,
  "downloadUrl": "/temp/outputs/encrypted-172159.pdf"
}`,
      responseJson400: `{
  "error": "Password parameter is required"
}`,
      curlSnippet: `curl -X POST "http://localhost:3000/encrypt" \\
  -F "password=SuperSecretPassword123" \\
  -F "pdf=@/path/to/document.pdf"`,
      jsSnippet: `const formData = new FormData();
formData.append('password', 'SuperSecretPassword123');
formData.append('pdf', pdfFile);

const res = await fetch('http://localhost:3000/encrypt', { method: 'POST', body: formData });`,
      pythonSnippet: `import requests

files = {'pdf': open('document.pdf', 'rb')}
data = {'password': 'SuperSecretPassword123'}
res = requests.post('http://localhost:3000/encrypt', files=files, data=data)`
    },
    {
      id: 'repair-pdf',
      category: 'pdf',
      method: 'POST',
      path: '/repair',
      title: 'Repair Corrupted PDF',
      description: 'Rebuilds broken PDF trailers, corrupted xref tables, and missing EOF markers.',
      authRequired: true,
      headers: {
        'Content-Type': 'multipart/form-data'
      },
      requestJson: `{
  "pdf": "<Corrupted PDF binary stream>"
}`,
      responseJson200: `{
  "success": true,
  "fixed": true,
  "downloadUrl": "/temp/outputs/repaired-172159.pdf"
}`,
      responseJson400: `{
  "error": "Unable to rebuild xref table for provided file"
}`,
      curlSnippet: `curl -X POST "http://localhost:3000/repair" \\
  -F "pdf=@/path/to/damaged.pdf"`,
      jsSnippet: `const formData = new FormData();
formData.append('pdf', damagedPdfFile);
const res = await fetch('http://localhost:3000/repair', { method: 'POST', body: formData });`,
      pythonSnippet: `import requests

files = {'pdf': open('damaged.pdf', 'rb')}
res = requests.post('http://localhost:3000/repair', files=files)`
    },
    {
      id: 'split-pdf',
      category: 'pdf',
      method: 'POST',
      path: '/split/pdf',
      title: 'Split PDF Pages',
      description: 'Extract specified page ranges or split a multi-page PDF into single-page documents.',
      authRequired: false,
      headers: {
        'Content-Type': 'multipart/form-data'
      },
      requestJson: `{
  "ranges": "1-3,5,8-10",
  "pdf": "<Binary PDF stream>"
}`,
      responseJson200: `{
  "success": true,
  "downloadUrl": "/temp/outputs/split-pages-172159.zip"
}`,
      responseJson400: `{
  "error": "Invalid range format"
}`,
      curlSnippet: `curl -X POST "http://localhost:3000/split/pdf" \\
  -F "ranges=1-3,5" \\
  -F "pdf=@/path/to/document.pdf"`,
      jsSnippet: `const formData = new FormData();
formData.append('ranges', '1-3,5');
formData.append('pdf', file);
const res = await fetch('http://localhost:3000/split/pdf', { method: 'POST', body: formData });`,
      pythonSnippet: `import requests
files = {'pdf': open('document.pdf', 'rb')}
data = {'ranges': '1-3,5'}
res = requests.post('http://localhost:3000/split/pdf', files=files, data=data)`
    },
    {
      id: 'peek-zip',
      category: 'archive',
      method: 'POST',
      path: '/peek/result',
      title: 'X-Ray ZIP Inspector',
      description: 'Uploads and extracts ZIP file structure into an isolated temporary workspace tree.',
      authRequired: true,
      headers: {
        'Content-Type': 'multipart/form-data'
      },
      requestJson: `{
  "archive": "<Binary .zip archive>"
}`,
      responseJson200: `{
  "success": true,
  "workspaceId": "ws_1721591829_4921",
  "tree": [
    { "name": "index.js", "type": "file", "size": 1420 },
    { "name": "src", "type": "directory", "children": [...] }
  ]
}`,
      responseJson400: `{
  "error": "No file uploaded"
}`,
      curlSnippet: `curl -X POST "http://localhost:3000/peek/result" \\
  -F "archive=@/path/to/project.zip"`,
      jsSnippet: `const formData = new FormData();
formData.append('archive', zipFile);
const res = await fetch('http://localhost:3000/peek/result', { method: 'POST', body: formData });`,
      pythonSnippet: `import requests
files = {'archive': open('project.zip', 'rb')}
res = requests.post('http://localhost:3000/peek/result', files=files)`
    },
    {
      id: 'peek-file-read',
      category: 'archive',
      method: 'GET',
      path: '/peek/file',
      title: 'Read Extracted File Content',
      description: 'Fetches raw text content for a specific file inside an active ZIP workspace.',
      authRequired: true,
      headers: {
        'Accept': 'application/json'
      },
      requestJson: `GET /peek/file?ws=ws_1721591829_4921&path=src/index.js`,
      responseJson200: `{
  "content": "console.log('Hello world!');"
}`,
      responseJson400: `{
  "error": "File is read-only or unsupported extension"
}`,
      curlSnippet: `curl -X GET "http://localhost:3000/peek/file?ws=ws_1721591829_4921&path=src/index.js"`,
      jsSnippet: `const res = await fetch('http://localhost:3000/peek/file?ws=ws_1721591829_4921&path=src/index.js');
const data = await res.json();`,
      pythonSnippet: `import requests
res = requests.get('http://localhost:3000/peek/file', params={'ws': 'ws_1721591829_4921', 'path': 'src/index.js'})
print(res.json())`
    },
    {
      id: 'auth-login',
      category: 'auth',
      method: 'POST',
      path: '/auth/login',
      title: 'Authenticate User Session',
      description: 'Authenticates user credentials and establishes an HTTP-only session cookie.',
      authRequired: false,
      headers: {
        'Content-Type': 'application/json'
      },
      requestJson: `{
  "email": "user@example.com",
  "password": "MySecretPassword"
}`,
      responseJson200: `{
  "success": true,
  "user": {
    "email": "user@example.com",
    "role": "developer"
  }
}`,
      responseJson400: `{
  "error": "Invalid email or password"
}`,
      curlSnippet: `curl -X POST "http://localhost:3000/auth/login" \\
  -H "Content-Type: application/json" \\
  -d '{"email":"user@example.com","password":"MySecretPassword"}'`,
      jsSnippet: `const res = await fetch('http://localhost:3000/auth/login', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ email: 'user@example.com', password: 'MySecretPassword' })
});`,
      pythonSnippet: `import requests
payload = {"email": "user@example.com", "password": "MySecretPassword"}
res = requests.post('http://localhost:3000/auth/login', json=payload)`
    }
  ];

  const filteredEndpoints = endpoints.filter(ep => {
    const matchesCategory = selectedCategory === 'all' || ep.category === selectedCategory;
    const matchesSearch = 
      ep.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      ep.path.toLowerCase().includes(searchQuery.toLowerCase()) ||
      ep.description.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesCategory && matchesSearch;
  });

  return (
    <div className="flex-1 bg-slate-50 min-h-screen pb-24">
      {/* HEADER SECTION */}
      <section className="bg-slate-900 text-white pt-12 pb-16 px-6 relative overflow-hidden">
        {/* Glow Effects */}
        <div className="absolute top-0 right-1/4 w-96 h-96 bg-blue-600/20 rounded-full blur-3xl pointer-events-none"></div>
        
        <div className="max-w-7xl mx-auto z-10 relative">
          <button
            onClick={() => onNavigate('developer-api')}
            className="inline-flex items-center gap-2 text-slate-400 hover:text-white transition text-xs font-bold uppercase tracking-wider mb-6"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to Developer Overview
          </button>

          <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
            <div>
              <div className="flex items-center gap-3 mb-2">
                <Terminal className="w-8 h-8 text-blue-400" />
                <h1 className="text-3xl md:text-5xl font-black tracking-tight">API Directory</h1>
              </div>
              <p className="text-slate-400 text-base md:text-lg max-w-2xl">
                Complete REST API specification, JSON schemas, headers, status codes, and code snippets.
              </p>
            </div>

            <div className="flex items-center gap-3 bg-slate-800/80 backdrop-blur border border-slate-700 p-2 rounded-2xl">
              <span className="text-xs text-slate-400 font-bold px-3">Base URL:</span>
              <span className="font-mono text-xs bg-slate-950 px-3 py-1.5 rounded-xl text-blue-300 font-semibold">
                http://localhost:3000
              </span>
            </div>
          </div>

          {/* SEARCH & FILTERS BAR */}
          <div className="mt-10 flex flex-col md:flex-row items-center gap-4">
            <div className="relative flex-1 w-full">
              <Search className="w-5 h-5 absolute left-4 top-1/2 -translate-y-1/2 text-slate-400" />
              <input
                type="text"
                placeholder="Search endpoints by path, title, or description (e.g. /convert, compress)..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-12 pr-4 py-3.5 bg-slate-800/90 border border-slate-700 rounded-2xl text-slate-100 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm font-medium"
              />
            </div>

            <div className="flex items-center gap-2 overflow-x-auto w-full md:w-auto pb-2 md:pb-0">
              {[
                { id: 'all', label: 'All Services', icon: Layers },
                { id: 'pdf', label: 'PDF Tools', icon: FileText },
                { id: 'ppt', label: 'PPT Tools', icon: Zap },
                { id: 'security', label: 'Security & Sanitize', icon: ShieldCheck },
                { id: 'archive', label: 'ZIP Inspector', icon: Archive },
                { id: 'auth', label: 'Auth & Session', icon: Key },
              ].map(tab => {
                const IconComponent = tab.icon;
                const isActive = selectedCategory === tab.id;
                return (
                  <button
                    key={tab.id}
                    onClick={() => setSelectedCategory(tab.id)}
                    className={`flex items-center gap-2 px-4 py-3 rounded-2xl text-xs font-bold transition whitespace-nowrap ${
                      isActive 
                        ? 'bg-blue-600 text-white shadow-lg shadow-blue-500/25' 
                        : 'bg-slate-800 text-slate-300 hover:bg-slate-700 hover:text-white'
                    }`}
                  >
                    <IconComponent className="w-3.5 h-3.5" />
                    {tab.label}
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      </section>

      {/* ENDPOINTS LIST */}
      <section className="max-w-7xl mx-auto px-6 pt-12">
        <div className="flex items-center justify-between mb-6">
          <p className="text-xs font-bold text-slate-500 uppercase tracking-widest">
            Showing {filteredEndpoints.length} Endpoint{filteredEndpoints.length !== 1 ? 's' : ''}
          </p>
        </div>

        {filteredEndpoints.length === 0 ? (
          <div className="bg-white rounded-3xl p-12 text-center border border-slate-200 shadow-sm">
            <Search className="w-12 h-12 text-slate-300 mx-auto mb-4" />
            <h3 className="text-xl font-bold text-slate-800 mb-2">No Matching Endpoints Found</h3>
            <p className="text-slate-500 text-sm max-w-md mx-auto mb-6">
              Try adjusting your search terms or selecting a different service category.
            </p>
            <button
              onClick={() => { setSearchQuery(''); setSelectedCategory('all'); }}
              className="px-6 py-2.5 bg-slate-900 text-white rounded-xl text-sm font-bold hover:bg-slate-800 transition"
            >
              Reset Filters
            </button>
          </div>
        ) : (
          <div className="space-y-8">
            {filteredEndpoints.map((ep) => {
              const activeTab = activeCodeTabs[ep.id] || 'curl';

              return (
                <div 
                  key={ep.id}
                  id={ep.id}
                  className="glass-card bg-white rounded-3xl border border-slate-200 shadow-sm overflow-hidden p-6 md:p-8"
                >
                  {/* Top Bar */}
                  <div className="flex flex-wrap items-center justify-between gap-4 pb-6 border-b border-slate-100">
                    <div>
                      <div className="flex items-center gap-3 mb-1">
                        <span className={`px-3 py-1 font-bold text-xs rounded-lg uppercase tracking-wider ${
                          ep.method === 'POST' ? 'bg-emerald-500 text-white' : 'bg-blue-600 text-white'
                        }`}>
                          {ep.method}
                        </span>
                        <h2 className="text-2xl font-black text-slate-900">{ep.title}</h2>
                        {ep.authRequired && (
                          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 bg-amber-50 text-amber-700 border border-amber-200 font-bold text-[10px] rounded-full">
                            <Lock className="w-3 h-3" />
                            Auth Required
                          </span>
                        )}
                      </div>
                      <p className="text-sm text-slate-600">{ep.description}</p>
                    </div>

                    <div className="font-mono text-sm bg-slate-950 text-emerald-400 px-4 py-2.5 rounded-xl border border-slate-800 flex items-center gap-3">
                      <span>{ep.path}</span>
                      <button
                        onClick={() => copyText(ep.path, ep.id + '_path')}
                        className="text-slate-400 hover:text-white transition"
                        title="Copy Route Path"
                      >
                        {copiedKey === ep.id + '_path' ? <Check className="w-4 h-4 text-emerald-400" /> : <Copy className="w-4 h-4" />}
                      </button>
                    </div>
                  </div>

                  {/* Body Content */}
                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mt-6">
                    {/* Left Column: Headers & JSON Payload Schemas */}
                    <div className="space-y-6">
                      {/* Headers */}
                      <div>
                        <span className="text-xs font-bold text-slate-400 uppercase tracking-widest block mb-2">Request Headers</span>
                        <div className="bg-slate-50 p-4 rounded-2xl border border-slate-200 space-y-1.5">
                          {Object.entries(ep.headers).map(([key, val]) => (
                            <div key={key} className="flex justify-between font-mono text-xs">
                              <span className="text-slate-500 font-semibold">{key}:</span>
                              <span className="text-slate-800">{val}</span>
                            </div>
                          ))}
                        </div>
                      </div>

                      {/* Request JSON */}
                      <div>
                        <div className="flex items-center justify-between mb-2">
                          <span className="text-xs font-bold text-slate-400 uppercase tracking-widest">Request Payload Format</span>
                          <button
                            onClick={() => copyText(ep.requestJson, ep.id + '_req')}
                            className="text-xs text-blue-600 hover:underline flex items-center gap-1 font-semibold"
                          >
                            {copiedKey === ep.id + '_req' ? <Check className="w-3.5 h-3.5 text-emerald-500" /> : <Copy className="w-3.5 h-3.5" />}
                            {copiedKey === ep.id + '_req' ? 'Copied' : 'Copy Payload'}
                          </button>
                        </div>
                        <div className="bg-slate-950 p-4 rounded-2xl border border-slate-800">
                          <pre className="font-mono text-xs text-blue-300 overflow-x-auto leading-relaxed">
                            {ep.requestJson}
                          </pre>
                        </div>
                      </div>

                      {/* Response JSON */}
                      <div>
                        <div className="flex items-center justify-between mb-2">
                          <span className="text-xs font-bold text-slate-400 uppercase tracking-widest">Response Format (200 OK)</span>
                          <button
                            onClick={() => copyText(ep.responseJson200, ep.id + '_res')}
                            className="text-xs text-blue-600 hover:underline flex items-center gap-1 font-semibold"
                          >
                            {copiedKey === ep.id + '_res' ? <Check className="w-3.5 h-3.5 text-emerald-500" /> : <Copy className="w-3.5 h-3.5" />}
                            {copiedKey === ep.id + '_res' ? 'Copied' : 'Copy Format'}
                          </button>
                        </div>
                        <div className="bg-slate-950 p-4 rounded-2xl border border-slate-800">
                          <pre className="font-mono text-xs text-emerald-400 overflow-x-auto leading-relaxed">
                            {ep.responseJson200}
                          </pre>
                        </div>
                      </div>
                    </div>

                    {/* Right Column: Code Snippets */}
                    <div className="bg-slate-950 rounded-2xl p-5 border border-slate-800 flex flex-col justify-between">
                      <div>
                        {/* Snippet Header / Tabs */}
                        <div className="flex items-center justify-between mb-4 pb-3 border-b border-slate-800">
                          <div className="flex items-center gap-2">
                            <Code2 className="w-4 h-4 text-indigo-400" />
                            <span className="text-xs font-bold text-slate-300 uppercase tracking-wider">Code Example</span>
                          </div>
                          
                          <div className="flex bg-slate-900 p-1 rounded-xl border border-slate-800">
                            {(['curl', 'js', 'python'] as const).map(tab => (
                              <button
                                key={tab}
                                onClick={() => setCodeTab(ep.id, tab)}
                                className={`px-3 py-1 text-xs font-bold rounded-lg uppercase transition ${
                                  activeTab === tab 
                                    ? 'bg-blue-600 text-white' 
                                    : 'text-slate-400 hover:text-white'
                                }`}
                              >
                                {tab === 'curl' ? 'cURL' : tab === 'js' ? 'JavaScript' : 'Python'}
                              </button>
                            ))}
                          </div>
                        </div>

                        {/* Code Display */}
                        <div className="relative">
                          <pre className="font-mono text-xs text-slate-200 overflow-x-auto p-2 leading-relaxed">
                            {activeTab === 'curl' && ep.curlSnippet}
                            {activeTab === 'js' && ep.jsSnippet}
                            {activeTab === 'python' && ep.pythonSnippet}
                          </pre>

                          <button
                            onClick={() => {
                              const code = activeTab === 'curl' ? ep.curlSnippet : activeTab === 'js' ? ep.jsSnippet : ep.pythonSnippet;
                              copyText(code, ep.id + '_' + activeTab);
                            }}
                            className="absolute top-0 right-0 p-2 text-slate-400 hover:text-white bg-slate-900/80 rounded-lg transition"
                            title="Copy Code"
                          >
                            {copiedKey === ep.id + '_' + activeTab ? <Check className="w-4 h-4 text-emerald-400" /> : <Copy className="w-4 h-4" />}
                          </button>
                        </div>
                      </div>

                      {/* Error Format Footer */}
                      <div className="mt-6 pt-4 border-t border-slate-900">
                        <span className="text-[10px] font-bold text-red-400 uppercase tracking-widest block mb-1">Error Response (400 Bad Request / 403 Forbidden)</span>
                        <pre className="font-mono text-[11px] text-red-300 bg-red-950/30 p-2.5 rounded-xl border border-red-900/30">
                          {ep.responseJson400}
                        </pre>
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </section>
    </div>
  );
};

export default ApiDirectory;
