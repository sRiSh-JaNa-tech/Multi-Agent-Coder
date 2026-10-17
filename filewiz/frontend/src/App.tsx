import { useState, useEffect } from 'react';
import Navbar from './components/Navbar';
import Dashboard from './components/Dashboard';
import Login from './components/Login';
import Signup from './components/Signup';
import ToolRedact from './components/ToolRedact';
import ToolEncrypt from './components/ToolEncrypt';
import ToolRepair from './components/ToolRepair';
import ToolSplit from './components/ToolSplit';
import ToolCompressPdf from './components/ToolCompressPdf';
import ToolCompressPpt from './components/ToolCompressPpt';
import ToolPeek from './components/ToolPeek';
import ToolConvert from './components/ToolConvert';
import DeveloperApi from './components/DeveloperApi';
import ApiDirectory from './components/ApiDirectory';
import api from './utils/api';

function App() {
  const [user, setUser] = useState<{ email: string } | null>(null);
  const [currentView, setCurrentView] = useState<string>('home');
  const [loadingSession, setLoadingSession] = useState(true);

  // ── Dynamic page titles for SEO ──────────────────────────────────────────
  const pageTitles: Record<string, string> = {
    home:          'FileWiz – Free PDF & Document Tools: Compress, Encrypt, Convert & More',
    login:         'Log In – FileWiz',
    signup:        'Create Account – FileWiz',
    redact:        'Redact PDF Sensitive Data Free – FileWiz',
    encrypt:       'Encrypt PDF with AES Password Protection – FileWiz',
    repair:        'Repair Corrupt PDF Files Online Free – FileWiz',
    convert:       'Convert PDF to PNG, DOCX, HTML Online Free – FileWiz',
    'compress-pdf':'Compress PDF File Size Online Free – FileWiz',
    split:         'Split PDF Pages Online Free – FileWiz',
    peek:          'ZIP File Inspector & Structure Viewer – FileWiz',
    'compress-ppt':'Compress PowerPoint PPTX Online Free – FileWiz',
    'developer-api':'Developer REST API – FileWiz',
    'api-directory':'Full API Directory & JSON Schemas – FileWiz',
  };

  useEffect(() => {
    const title = pageTitles[currentView] ?? 'FileWiz – Document Processing Suite';
    document.title = title;
    // Update og:title dynamically for share previews after navigation
    const ogTitle = document.querySelector('meta[property="og:title"]');
    if (ogTitle) ogTitle.setAttribute('content', title);
  }, [currentView]);

  // Load session on application startup
  useEffect(() => {
    const fetchSession = async () => {
      try {
        const response = await api.get('/auth/session');
        if (response.data.loggedIn && response.data.user) {
          setUser(response.data.user);
        }
      } catch (err) {
        console.log('No active session found or backend not running yet.', err);
      } finally {
        setLoadingSession(false);
      }
    };
    fetchSession();
  }, []);


  const handleLogout = async () => {
    try {
      await api.get('/auth/logout');
      setUser(null);
      setCurrentView('home');
    } catch (err) {
      console.error('Logout error:', err);
    }
  };

  const renderActiveView = () => {
    switch (currentView) {
      case 'home':
        return <Dashboard onNavigate={setCurrentView} />;
      case 'login':
        return <Login onLoginSuccess={setUser} onNavigate={setCurrentView} />;
      case 'signup':
        return <Signup onNavigate={setCurrentView} />;
      case 'redact':
        return <ToolRedact />;
      case 'encrypt':
        return <ToolEncrypt />;
      case 'repair':
        return <ToolRepair />;
      case 'split':
        return <ToolSplit />;
      case 'compress-pdf':
        return <ToolCompressPdf />;
      case 'compress-ppt':
        return <ToolCompressPpt />;
      case 'peek':
        return <ToolPeek />;
      case 'convert':
        return <ToolConvert />;
      case 'developer-api':
        return <DeveloperApi onNavigate={setCurrentView} />;
      case 'api-directory':
        return <ApiDirectory onNavigate={setCurrentView} />;
      default:
        return <Dashboard onNavigate={setCurrentView} />;
    }
  };

  if (loadingSession) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50">
        <div className="text-center">
          <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-4 text-slate-500 font-medium text-sm">Loading FileWiz Suite...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex flex-col bg-slate-50 overflow-x-hidden w-full max-w-full">
      <Navbar
        user={user}
        currentView={currentView}
        onNavigate={setCurrentView}
        onLogout={handleLogout}
      />
      <main className="flex-1 flex flex-col">
        {renderActiveView()}
      </main>
    </div>
  );
}

export default App;
