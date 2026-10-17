import React, { useState } from 'react';
import { ChevronDown, LogOut, LogIn, UserPlus, Menu } from 'lucide-react';

interface NavbarProps {
  user: { email: string } | null;
  currentView: string;
  onNavigate: (view: string) => void;
  onLogout: () => void;
}

const Navbar: React.FC<NavbarProps> = ({ user, currentView, onNavigate, onLogout }) => {
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const tools = [
    { name: 'Redact Information', id: 'redact', icon: '/assets/storage.png' },
    { name: 'Encrypt PDF', id: 'encrypt', icon: '/assets/encrpyted-file.png' },
    { name: 'Repair Structure', id: 'repair', icon: '/assets/repair-tools.png' },
    { name: 'Split Pages', id: 'split', icon: '/assets/document.png' },
    { name: 'Compress PPT', id: 'compress-ppt', icon: '/assets/powerpoint.png' },
  ];

  const handleToolClick = (toolId: string) => {
    onNavigate(toolId);
    setDropdownOpen(false);
    setMobileMenuOpen(false);
  };

  return (
    <nav className="bg-white border-b border-gray-200 sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between h-16 items-center">
          {/* Logo */}
          <div className="flex items-center space-x-2 cursor-pointer" onClick={() => onNavigate('home')}>
            <img src="/assets/open-folder.png" alt="FileWiz Logo" className="h-7 w-7" />
            <span className="text-xl font-bold text-blue-600">FileWiz</span>
          </div>

          {/* Desktop Links */}
          <div className="hidden md:flex items-center space-x-8">
            <button
              onClick={() => onNavigate('home')}
              className={`text-sm font-medium transition-colors ${currentView === 'home' ? 'text-blue-600 font-bold' : 'text-gray-700 hover:text-blue-600'}`}
            >
              Home
            </button>
            <button
              onClick={() => onNavigate('peek')}
              className={`text-sm font-medium transition-colors ${currentView === 'peek' ? 'text-blue-600 font-bold' : 'text-gray-700 hover:text-blue-600'}`}
            >
              Peek
            </button>
            <button
              onClick={() => onNavigate('convert')}
              className={`text-sm font-medium transition-colors ${currentView === 'convert' ? 'text-blue-600 font-bold' : 'text-gray-700 hover:text-blue-600'}`}
            >
              Convert PDF
            </button>
            <button
              onClick={() => onNavigate('compress-pdf')}
              className={`text-sm font-medium transition-colors ${currentView === 'compress-pdf' ? 'text-blue-600 font-bold' : 'text-gray-700 hover:text-blue-600'}`}
            >
              Compress PDF
            </button>
            <button
              onClick={() => onNavigate('developer-api')}
              className={`text-sm font-medium transition-colors ${currentView === 'developer-api' || currentView === 'api-directory' ? 'text-blue-600 font-bold' : 'text-gray-700 hover:text-blue-600'}`}
            >
              Developer API
            </button>

            {/* Dropdown Menu */}
            <div className="relative">
              <button
                onClick={() => setDropdownOpen(!dropdownOpen)}
                onBlur={() => setTimeout(() => setDropdownOpen(false), 200)}
                className="flex items-center text-sm font-medium text-gray-700 hover:text-blue-600 focus:outline-none"
              >
                More Tools
                <ChevronDown className={`ml-1 w-4 h-4 transition-transform duration-200 ${dropdownOpen ? 'rotate-180' : ''}`} />
              </button>

              {dropdownOpen && (
                <div className="absolute right-0 mt-2 w-56 bg-white border border-gray-100 rounded-2xl shadow-2xl py-3 z-[100] animate-in fade-in slide-in-from-top-2">
                  <div className="px-4 py-2 text-[10px] font-black text-slate-400 uppercase tracking-widest border-b border-slate-50 mb-1">
                    Safety & Structure
                  </div>
                  {tools.slice(0, 3).map((tool) => (
                    <button
                      key={tool.id}
                      onClick={() => handleToolClick(tool.id)}
                      className="w-full flex items-center gap-3 px-4 py-2.5 text-left text-sm text-slate-600 hover:bg-blue-50 hover:text-blue-600 transition-all"
                    >
                      <img src={tool.icon} alt={tool.name} className="w-5 h-5 object-contain" />
                      {tool.name}
                    </button>
                  ))}
                  <div className="px-4 py-2 text-[10px] font-black text-slate-400 uppercase tracking-widest border-b border-slate-50 mt-2 mb-1">
                    Optimization
                  </div>
                  {tools.slice(3).map((tool) => (
                    <button
                      key={tool.id}
                      onClick={() => handleToolClick(tool.id)}
                      className="w-full flex items-center gap-3 px-4 py-2.5 text-left text-sm text-slate-600 hover:bg-blue-50 hover:text-blue-600 transition-all"
                    >
                      <img src={tool.icon} alt={tool.name} className="w-5 h-5 object-contain" />
                      {tool.name}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Desktop CTA */}
          <div className="hidden md:flex items-center space-x-3">
            {user ? (
              <>
                <span className="text-sm font-medium text-gray-600">
                  Welcome, {user.email.split('@')[0]}
                </span>
                <button
                  onClick={onLogout}
                  className="flex items-center gap-1.5 px-4 py-2 text-sm text-red-600 border border-red-200 rounded-lg hover:bg-red-50 transition"
                >
                  <LogOut className="w-4 h-4" />
                  Logout
                </button>
              </>
            ) : (
              <>
                <button
                  onClick={() => onNavigate('login')}
                  className="flex items-center gap-1.5 px-4 py-2 text-sm text-blue-600 border border-blue-600 rounded-lg hover:bg-blue-50 transition"
                >
                  <LogIn className="w-4 h-4" />
                  Login
                </button>
                <button
                  onClick={() => onNavigate('signup')}
                  className="flex items-center gap-1.5 px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition"
                >
                  <UserPlus className="w-4 h-4" />
                  Sign Up
                </button>
              </>
            )}
          </div>

          {/* Mobile Menu Button */}
          <button
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            className="md:hidden inline-flex items-center justify-center p-2 rounded-lg text-gray-600 hover:bg-gray-100 focus:outline-none"
          >
            <Menu className="w-6 h-6" />
          </button>
        </div>
      </div>

      {/* Mobile Menu */}
      {mobileMenuOpen && (
        <div className="md:hidden border-t bg-white px-4 py-4 space-y-3 shadow-lg">
          <button
            onClick={() => { onNavigate('home'); setMobileMenuOpen(false); }}
            className="block w-full text-left text-gray-700 hover:text-blue-600 font-medium py-1"
          >
            Home
          </button>
          <button
            onClick={() => { onNavigate('peek'); setMobileMenuOpen(false); }}
            className="block w-full text-left text-gray-700 hover:text-blue-600 font-medium py-1"
          >
            Peek
          </button>
          <button
            onClick={() => { onNavigate('convert'); setMobileMenuOpen(false); }}
            className="block w-full text-left text-gray-700 hover:text-blue-600 font-medium py-1"
          >
            Convert PDF
          </button>
          <button
            onClick={() => { onNavigate('compress-pdf'); setMobileMenuOpen(false); }}
            className="block w-full text-left text-gray-700 hover:text-blue-600 font-medium py-1"
          >
            Compress PDF
          </button>
          <button
            onClick={() => { onNavigate('developer-api'); setMobileMenuOpen(false); }}
            className="block w-full text-left text-gray-700 hover:text-blue-600 font-medium py-1"
          >
            Developer API
          </button>

          <div className="border-t border-gray-100 my-2 pt-2">
            <p className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-2">More Tools</p>
            {tools.map((tool) => (
              <button
                key={tool.id}
                onClick={() => handleToolClick(tool.id)}
                className="flex items-center gap-2 w-full text-left text-sm text-gray-600 hover:text-blue-600 py-2"
              >
                <img src={tool.icon} alt={tool.name} className="w-4 h-4 object-contain" />
                {tool.name}
              </button>
            ))}
          </div>

          <div className="border-t border-gray-100 pt-2 flex flex-col gap-2">
            {user ? (
              <>
                <span className="text-sm font-medium text-gray-600">
                  Welcome, {user.email.split('@')[0]}
                </span>
                <button
                  onClick={() => { onLogout(); setMobileMenuOpen(false); }}
                  className="flex items-center justify-center gap-1.5 px-4 py-2 w-full text-sm text-red-600 border border-red-200 rounded-lg hover:bg-red-50 transition"
                >
                  <LogOut className="w-4 h-4" />
                  Logout
                </button>
              </>
            ) : (
              <>
                <button
                  onClick={() => { onNavigate('login'); setMobileMenuOpen(false); }}
                  className="flex items-center justify-center gap-1.5 px-4 py-2 w-full text-sm text-blue-600 border border-blue-600 rounded-lg hover:bg-blue-50 transition"
                >
                  <LogIn className="w-4 h-4" />
                  Login
                </button>
                <button
                  onClick={() => { onNavigate('signup'); setMobileMenuOpen(false); }}
                  className="flex items-center justify-center gap-1.5 px-4 py-2 w-full text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition"
                >
                  <UserPlus className="w-4 h-4" />
                  Sign Up
                </button>
              </>
            )}
          </div>
        </div>
      )}
    </nav>
  );
};

export default Navbar;
