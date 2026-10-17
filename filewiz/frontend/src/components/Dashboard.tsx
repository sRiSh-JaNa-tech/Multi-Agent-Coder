import React from 'react';

interface DashboardProps {
  onNavigate: (view: string) => void;
}

const Dashboard: React.FC<DashboardProps> = ({ onNavigate }) => {
  const coreServices = [
    {
      id: 'redact',
      name: 'Redact Information',
      desc: 'Permanently sanitize sensitive data. Hide text, images, and metadata securely.',
      icon: '/assets/storage.png',
    },
    {
      id: 'encrypt',
      name: 'Encrypt PDF',
      desc: 'Protect your documents with military-grade AES encryption and password locks.',
      icon: '/assets/encrpyted-file.png',
    },
    {
      id: 'repair',
      name: 'Repair Structure',
      desc: 'Detect corruption and rebuild broken PDF headers and cross-reference tables.',
      icon: '/assets/repair-tools.png',
    },
    {
      id: 'convert',
      name: 'Convert Format',
      desc: 'Transform PDFs into high-quality images (PNG, JPEG), HTML, or DOCX documents.',
      icon: '/assets/convert.png',
    },
    {
      id: 'compress-pdf',
      name: 'Compress PDF',
      desc: 'Reduce file size without losing quality. Perfect for email attachments.',
      icon: '/assets/folder.png',
    },
    {
      id: 'split',
      name: 'Split Pages',
      desc: 'Extract specific pages or split a large document into multiple smaller files.',
      icon: '/assets/document.png',
    },
    {
      id: 'peek',
      name: 'X-Ray ZIP Peek',
      desc: 'Inspect file internals and structure without opening dangerous executables.',
      icon: '/assets/stare.png',
    },
    {
      id: 'compress-ppt',
      name: 'Shrink Slides',
      desc: 'Optimize PowerPoint presentations for web sharing and faster loading.',
      icon: '/assets/powerpoint.png',
    },
  ];

  return (
    <div className="flex-1 flex flex-col">
      {/* HERO SECTION */}
      <section className="relative flex flex-col items-center justify-center overflow-hidden bg-white px-6" style={{ minHeight: 'calc(100vh - 64px)' }}>
        {/* Dynamic Abstract Background Elements */}
        <div className="absolute top-0 right-1/4 w-[30rem] h-[30rem] bg-gradient-to-tr from-cyan-100 to-blue-200 rounded-full blur-[100px] opacity-60 animate-float-slow pointer-events-none"></div>
        <div className="absolute bottom-10 left-1/4 w-[25rem] h-[25rem] bg-gradient-to-bl from-purple-100 to-pink-200 rounded-full blur-[100px] opacity-60 animate-float-medium pointer-events-none"></div>

        <div className="relative z-10 text-center max-w-5xl mx-auto flex flex-col items-center py-16">
          <div className="mb-6 inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-white/40 backdrop-blur-md border border-slate-100 shadow-sm shadow-blue-500/5 hover:scale-105 transition-transform cursor-default">
            <span className="flex h-2 w-2 rounded-full bg-blue-500 animate-pulse"></span>
            <span className="text-xs font-bold tracking-widest text-slate-500 uppercase">FileWiz Suite v2.0</span>
          </div>
          
          <h1 className="text-5xl md:text-6xl lg:text-7xl font-black tracking-tighter text-slate-800 mb-6 leading-tight max-w-4xl mx-auto">
            Free PDF &amp; document tools <br className="hidden md:block" />
            that <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-600 via-indigo-500 to-violet-600 drop-shadow-sm">actually work.</span>
          </h1>
          
          <p className="text-lg md:text-xl text-slate-500 max-w-2xl mb-10 leading-relaxed font-medium">
            Compress, encrypt, convert, and repair your files — all processed privately, never uploaded to third-party servers.
          </p>

          <div className="flex flex-wrap gap-4 justify-center">
            <a href="#services" aria-label="Browse all document tools" className="px-10 py-4 bg-slate-900 text-white rounded-2xl font-bold text-lg hover:bg-slate-800 hover:-translate-y-1 transition-all duration-300 shadow-xl shadow-slate-900/20">
              Get Started
            </a>
            <button onClick={() => onNavigate('peek')} aria-label="Open ZIP File Inspector tool" className="px-10 py-4 bg-white text-slate-700 border border-slate-200 rounded-2xl font-bold text-lg hover:bg-slate-50 hover:-translate-y-1 transition-all duration-300 shadow-lg shadow-slate-200/50">
              ZIP Inspector
            </button>
          </div>
        </div>
      </section>

      {/* ADVERTISEMENT BANNER (Thin) */}
      <div className="bg-slate-900 text-white py-3 overflow-hidden">
        <div className="max-w-7xl mx-auto px-6 flex items-center justify-center gap-4 text-sm font-medium">
          <span className="bg-indigo-500 text-[10px] font-bold px-2 py-0.5 rounded uppercase">New</span>
          <p>Pro users can now process files up to 2GB! <a href="#" className="underline hover:text-blue-300 ml-1">Upgrade Plan</a></p>
        </div>
      </div>

      {/* SERVICES GRID */}
      <section id="services" aria-labelledby="services-heading" className="max-w-7xl mx-auto px-6 py-20">
        <div className="flex items-center justify-between mb-12">
          <div>
            <h2 id="services-heading" className="text-3xl font-black text-slate-800">Free Document Processing Tools</h2>
            <p className="text-slate-500 mt-1">Compress, encrypt, convert, split, redact, and repair your files — all in your browser.</p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {coreServices.map((srv) => (
            <button
              key={srv.id}
              onClick={() => onNavigate(srv.id)}
              aria-label={`Open ${srv.name} tool`}
              className="glass-card rounded-3xl p-6 text-left group cursor-pointer focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <div className="icon-holder w-16 h-16 mb-6">
                <img
                  src={srv.icon}
                  alt={`${srv.name} icon`}
                  className="w-8 h-8 opacity-80 group-hover:opacity-100 transition-opacity"
                  onError={(e) => {
                    (e.target as HTMLImageElement).src = `https://placehold.co/400x400/BFDBFE/1E40AF?text=${srv.name.substring(0, 2).toUpperCase()}`;
                  }}
                />
              </div>
              <h3 className="text-xl font-bold text-slate-800 mb-2 group-hover:text-blue-600 transition-colors">
                {srv.name}
              </h3>
              <p className="text-sm text-slate-500 leading-relaxed">
                {srv.desc}
              </p>
            </button>
          ))}
        </div>
      </section>

      {/* LARGE ADVERTISEMENT / PROMO */}
      <section className="max-w-7xl mx-auto px-6 pb-20">
        <div className="ad-banner rounded-3xl p-8 md:p-12 text-center md:text-left flex flex-col md:flex-row items-center justify-between gap-8">
          <div className="ad-shine"></div>
          <div className="z-10 max-w-xl">
            <h2 className="text-3xl font-black text-white mb-4">Go Limitless with FileWiz Pro</h2>
            <p className="text-slate-300 text-lg mb-6">
              Unlock batch processing, higher file size limits, and priority cloud support.
              Start your 14-day free trial today.
            </p>
            <div className="flex flex-wrap gap-4 justify-center md:justify-start">
              <button className="bg-blue-600 hover:bg-blue-500 text-white px-6 py-3 rounded-xl font-bold transition-all shadow-lg">
                Get Started
              </button>
              <button className="bg-transparent border border-slate-600 text-slate-300 hover:text-white hover:border-white px-6 py-3 rounded-xl font-bold transition-all">
                View Pricing
              </button>
            </div>
          </div>
          <div className="z-10 relative">
            <img 
              src="/assets/Gold-Folder.jpg" 
              alt="FileWiz Pro Gold Folder" 
              className="w-48 h-48 md:w-56 md:h-56 object-cover rounded-2xl border border-white/20 shadow-2xl hover:scale-105 transition-transform duration-300"
            />
            <div className="absolute -bottom-6 -right-6 w-32 h-32 bg-blue-500 rounded-full blur-3xl opacity-30"></div>
          </div>
        </div>
      </section>
    </div>
  );
};

export default Dashboard;
