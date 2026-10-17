import React, { useState, useEffect, useRef } from 'react';
import { Upload, FileText, AlertCircle, Eye, Trash2, ShieldAlert, ArrowRight } from 'lucide-react';
import api from '../utils/api';

declare global {
  interface Window {
    pdfjsLib: any;
  }
}

interface RedactionBox {
  id: number;
  page: number;
  x: number;
  y: number;
  width: number;
  height: number;
  displayX: number;
  displayY: number;
  displayWidth: number;
  displayHeight: number;
}

const ToolRedact: React.FC = () => {
  const [file, setFile] = useState<File | null>(null);
  const [uploadedFilename, setUploadedFilename] = useState<string | null>(null);
  const [pdfUrl, setPdfUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [redactionBoxes, setRedactionBoxes] = useState<RedactionBox[]>([]);
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(0);

  const containerRef = useRef<HTMLDivElement>(null);
  const isDrawingRef = useRef(false);
  const startXRef = useRef(0);
  const startYRef = useRef(0);
  const currentBoxRef = useRef<HTMLDivElement | null>(null);
  const scale = 1.3;

  // Load PDF.js script dynamically
  useEffect(() => {
    if (uploadedFilename && pdfUrl) {
      const script = document.createElement('script');
      script.src = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.min.js';
      script.async = true;
      script.onload = () => {
        window.pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';
        loadPdfPages();
      };
      document.body.appendChild(script);

      return () => {
        document.body.removeChild(script);
      };
    }
  }, [uploadedFilename, pdfUrl]);

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
    formData.append('pdf', file);

    try {
      const response = await api.post('/redaction/upload', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });

      if (response.data.success) {
        setUploadedFilename(response.data.filename);
        // Point to absolute URL on local server
        setPdfUrl(`http://localhost:3000${response.data.pdfUrl}`);
      } else {
        throw new Error('Upload failed');
      }
    } catch (err: any) {
      console.error('Upload redaction PDF error:', err);
      setError(err.response?.data?.error || 'Failed to upload PDF. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const loadPdfPages = async () => {
    if (!pdfUrl || !window.pdfjsLib || !containerRef.current) return;

    try {
      containerRef.current.innerHTML = '';
      const loadingTask = window.pdfjsLib.getDocument(pdfUrl);
      const pdf = await loadingTask.promise;
      setTotalPages(pdf.numPages);

      for (let pageNum = 1; pageNum <= pdf.numPages; pageNum++) {
        await renderPage(pdf, pageNum);
      }
    } catch (err: any) {
      console.error('PDF.js render error:', err);
      setError('Failed to load PDF preview in browser.');
    }
  };

  const renderPage = async (pdf: any, pageNum: number) => {
    const page = await pdf.getPage(pageNum);
    const viewport = page.getViewport({ scale });

    const wrapper = document.createElement('div');
    wrapper.className = 'page-wrapper relative border shadow-sm mb-6 bg-white inline-block select-none';
    wrapper.dataset.pageNum = pageNum.toString();
    wrapper.style.width = `${viewport.width}px`;
    wrapper.style.height = `${viewport.height}px`;

    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');
    canvas.width = viewport.width;
    canvas.height = viewport.height;
    canvas.className = 'block absolute top-0 left-0 z-0';

    const overlay = document.createElement('div');
    overlay.className = 'absolute top-0 left-0 right-0 bottom-0 z-10 cursor-crosshair';
    overlay.style.width = `${viewport.width}px`;
    overlay.style.height = `${viewport.height}px`;

    wrapper.appendChild(canvas);
    wrapper.appendChild(overlay);
    containerRef.current?.appendChild(wrapper);

    await page.render({ canvasContext: ctx, viewport }).promise;

    setupDrawing(wrapper, overlay, pageNum);
  };

  const setupDrawing = (wrapper: HTMLDivElement, overlay: HTMLDivElement, pageNum: number) => {
    overlay.addEventListener('mousedown', (e) => {
      if (e.button !== 0) return; // Left click only
      isDrawingRef.current = true;
      const rect = wrapper.getBoundingClientRect();
      startXRef.current = e.clientX - rect.left;
      startYRef.current = e.clientY - rect.top;

      const box = document.createElement('div');
      box.className = 'absolute bg-black opacity-50 border border-white z-20 pointer-events-none';
      box.style.left = `${startXRef.current}px`;
      box.style.top = `${startYRef.current}px`;
      wrapper.appendChild(box);
      currentBoxRef.current = box;
    });

    overlay.addEventListener('mousemove', (e) => {
      if (!isDrawingRef.current || !currentBoxRef.current) return;
      const rect = wrapper.getBoundingClientRect();
      const curX = Math.max(0, Math.min(e.clientX - rect.left, rect.width));
      const curY = Math.max(0, Math.min(e.clientY - rect.top, rect.height));

      const left = Math.min(startXRef.current, curX);
      const top = Math.min(startYRef.current, curY);
      const width = Math.abs(curX - startXRef.current);
      const height = Math.abs(curY - startYRef.current);

      currentBoxRef.current.style.left = `${left}px`;
      currentBoxRef.current.style.top = `${top}px`;
      currentBoxRef.current.style.width = `${width}px`;
      currentBoxRef.current.style.height = `${height}px`;
    });

    overlay.addEventListener('mouseup', () => {
      if (!isDrawingRef.current || !currentBoxRef.current) return;
      isDrawingRef.current = false;

      const boxEl = currentBoxRef.current;
      const finalRect = {
        x: parseFloat(boxEl.style.left),
        y: parseFloat(boxEl.style.top),
        width: parseFloat(boxEl.style.width),
        height: parseFloat(boxEl.style.height),
      };

      boxEl.remove();
      currentBoxRef.current = null;

      if (finalRect.width < 5 || finalRect.height < 5) return;

      const newBox: RedactionBox = {
        id: Date.now() + Math.random(),
        page: pageNum,
        x: finalRect.x / scale,
        y: finalRect.y / scale,
        width: finalRect.width / scale,
        height: finalRect.height / scale,
        displayX: finalRect.x,
        displayY: finalRect.y,
        displayWidth: finalRect.width,
        displayHeight: finalRect.height,
      };

      setRedactionBoxes((prev) => [...prev, newBox]);
      drawRedactionOverlay(wrapper, newBox);
    });
  };

  const drawRedactionOverlay = (wrapper: HTMLDivElement, box: RedactionBox) => {
    const div = document.createElement('div');
    div.className = 'redaction-box absolute bg-black opacity-70 z-20 cursor-pointer hover:opacity-90 transition';
    div.style.left = `${box.displayX}px`;
    div.style.top = `${box.displayY}px`;
    div.style.width = `${box.displayWidth}px`;
    div.style.height = `${box.displayHeight}px`;
    div.dataset.boxId = box.id.toString();
    div.title = 'Click to remove selection';

    div.onclick = (e) => {
      e.stopPropagation();
      removeBox(box.id);
    };

    wrapper.appendChild(div);
  };

  const removeBox = (id: number) => {
    setRedactionBoxes((prev) => prev.filter((b) => b.id !== id));
    const overlay = document.querySelector(`[data-box-id="${id}"]`);
    overlay?.remove();
  };

  const submitRedactions = async () => {
    if (redactionBoxes.length === 0 || !uploadedFilename) return;

    setProcessing(true);
    setError(null);

    const payload = redactionBoxes.map((b) => ({
      page: b.page,
      x: b.x,
      y: b.y,
      width: b.width,
      height: b.height,
    }));

    try {
      const response = await api.post(
        '/redaction/execute',
        {
          filename: uploadedFilename,
          redactions: payload,
        },
        {
          responseType: 'blob',
        }
      );

      const blob = new Blob([response.data], { type: 'application/pdf' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'redacted_document.pdf';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);

      alert('Redacted PDF downloaded successfully!');
      resetTool();
    } catch (err: any) {
      console.error('Redaction apply error:', err);
      setError('Redaction process failed. Please verify coordinates and try again.');
    } finally {
      setProcessing(false);
    }
  };

  const resetTool = () => {
    setFile(null);
    setUploadedFilename(null);
    setPdfUrl(null);
    setRedactionBoxes([]);
    setError(null);
    setLoading(false);
    setProcessing(false);
  };

  // Monitor scroll for page counter
  const handleScroll = (e: React.UIEvent<HTMLDivElement>) => {
    const container = e.currentTarget;
    const wrappers = container.querySelectorAll('.page-wrapper');
    const containerTop = container.getBoundingClientRect().top;
    let current = 1;

    wrappers.forEach((w: any) => {
      const rect = w.getBoundingClientRect();
      if (rect.top - containerTop < 100) {
        current = parseInt(w.dataset.pageNum);
      }
    });

    setCurrentPage(current);
  };

  return (
    <div className="flex-1 flex flex-col h-[calc(100vh-4rem)]">
      {!uploadedFilename ? (
        <div className="flex-1 flex items-center justify-center p-6 bg-slate-50">
          <div className="w-full max-w-xl bg-white rounded-3xl shadow-xl p-8 border border-slate-100">
            <h2 className="text-3xl font-black text-center text-slate-800 font-display">
              Redaction Studio
            </h2>
            <p className="text-center text-slate-500 mt-2 text-sm">
              Upload a document to visually mask and scrub sensitive information
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
                  id="redact-file"
                  type="file"
                  accept=".pdf"
                  onChange={handleFileChange}
                  className="hidden"
                  required
                />
                <label htmlFor="redact-file" className="flex flex-col items-center justify-center w-full h-full cursor-pointer">
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
                        <p className="text-slate-700 font-medium">Drag & drop your PDF file</p>
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
                {loading ? 'Uploading...' : 'Launch Redaction Studio'}
              </button>
            </form>
          </div>
        </div>
      ) : (
        <div className="flex-1 flex flex-col lg:flex-row overflow-hidden bg-slate-100/40">
          {/* Main Drawing Area */}
          <div className="flex-1 flex flex-col min-h-0">
            <div className="bg-white border-b border-slate-200 px-6 py-4 flex items-center justify-between shadow-sm">
              <div>
                <h3 className="text-lg font-extrabold text-slate-800">Redaction Canvas</h3>
                <p className="text-xs text-slate-400">Drag/draw coordinates over areas to redact</p>
              </div>
              <div className="text-xs font-semibold text-slate-500 bg-slate-50 border border-slate-150 px-3 py-1.5 rounded-xl">
                Page {currentPage} of {totalPages}
              </div>
            </div>

            {/* Scrollable Container for PDF Canvases */}
            <div
              ref={containerRef}
              onScroll={handleScroll}
              className="flex-1 overflow-y-auto p-8 space-y-6 text-center select-none"
            >
              {/* PDF canvases and overlay drawings are injected here */}
            </div>
          </div>

          {/* Sidebar Controls */}
          <div className="w-full lg:w-96 bg-white border-t lg:border-t-0 lg:border-l border-slate-200 flex flex-col min-h-0">
            <div className="px-6 py-5 border-b border-slate-150 flex items-center justify-between">
              <h3 className="text-xs font-black text-slate-800 uppercase tracking-wider">Selected Targets</h3>
              <span className="bg-rose-50 text-rose-600 text-[10px] font-extrabold px-2.5 py-1 rounded-full border border-rose-100">
                {redactionBoxes.length} {redactionBoxes.length === 1 ? 'Area' : 'Areas'}
              </span>
            </div>

            {/* Selection List */}
            <div className="flex-1 overflow-y-auto px-6 py-4">
              {redactionBoxes.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-20 text-center">
                  <div className="w-12 h-12 bg-slate-50 rounded-full flex items-center justify-center mb-3">
                    <Eye className="w-6 h-6 text-slate-300" />
                  </div>
                  <p className="text-slate-400 text-xs font-bold">No redaction markers placed</p>
                  <p className="text-slate-350 text-[10px] mt-1">Drag anywhere on the PDF pages to select</p>
                </div>
              ) : (
                <ul className="space-y-3">
                  {redactionBoxes.map((b) => (
                    <li
                      key={b.id}
                      className="group flex justify-between items-center bg-slate-50 p-3 rounded-2xl border border-slate-150 hover:border-rose-200 hover:shadow-sm transition-all"
                    >
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-xl bg-rose-50 flex items-center justify-center text-[10px] font-black text-rose-500 border border-rose-100">
                          P{b.page}
                        </div>
                        <div className="flex flex-col text-left">
                          <span className="text-xs font-bold text-slate-700">Area coordinates</span>
                          <span className="text-[10px] text-slate-400">
                            X: {b.x.toFixed(0)}, Y: {b.y.toFixed(0)}
                          </span>
                        </div>
                      </div>
                      <button
                        onClick={() => removeBox(b.id)}
                        className="text-slate-300 hover:text-rose-500 p-1.5 hover:bg-white rounded-lg transition-all"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            {/* Apply Area */}
            <div className="p-6 border-t border-slate-150 space-y-4">
              <div className="flex gap-3 p-4 bg-amber-50/50 rounded-2xl border border-amber-100 text-left">
                <ShieldAlert className="w-5 h-5 text-amber-500 flex-shrink-0 mt-0.5" />
                <div>
                  <h4 className="text-xs font-bold text-amber-800">Permanent Removal</h4>
                  <p className="text-[10px] text-amber-600 mt-0.5 leading-relaxed">
                    This will permanently scrub pixels and structure references of specified coordinates.
                  </p>
                </div>
              </div>

              <button
                onClick={submitRedactions}
                disabled={redactionBoxes.length === 0 || processing}
                className="w-full bg-rose-500 hover:bg-rose-600 disabled:bg-slate-300 text-white py-3.5 rounded-xl font-bold transition shadow-lg flex items-center justify-center gap-2"
              >
                <span>{processing ? 'Processing...' : 'Apply Redactions'}</span>
                <ArrowRight className="w-4 h-4" />
              </button>

              <button
                onClick={resetTool}
                className="w-full text-center text-xs font-bold text-slate-400 hover:text-slate-500 uppercase tracking-widest pt-2"
              >
                Discard & Upload New
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ToolRedact;
