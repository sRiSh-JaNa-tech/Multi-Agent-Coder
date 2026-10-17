import React, { useState } from 'react';
import api from '../utils/api';

interface LoginProps {
  onLoginSuccess: (user: { email: string }) => void;
  onNavigate: (view: string) => void;
}

const Login: React.FC<LoginProps> = ({ onLoginSuccess, onNavigate }) => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      const response = await api.post('/auth/login', { email, password });
      
      // If we adapted the backend, it will return JSON. Let's see what the backend does.
      // If the backend returned a redirect, we can check if it succeeded.
      // If we update the backend to return JSON, it will return `{ success: true, user: { email } }` or similar.
      if (response.data.error) {
        setError(response.data.error);
      } else {
        // Successful login
        onLoginSuccess({ email });
        onNavigate('home');
      }
    } catch (err: any) {
      console.error('Login error:', err);
      setError(err.response?.data?.error || 'Invalid email or password');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex-1 flex flex-col items-center justify-center px-4 bg-slate-50 w-full py-12">
      <div className="w-full max-w-md bg-white rounded-3xl shadow-xl border border-slate-100 p-8">
        <h2 className="text-3xl font-black text-center text-slate-800">
          Welcome Back
        </h2>
        <p className="text-center text-slate-500 mt-2 text-sm">
          Login to continue using FileWiz Suite
        </p>

        {error && (
          <div className="mt-6 bg-rose-50 border border-rose-200 text-rose-600 px-4 py-3 rounded-xl text-center text-sm font-medium">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="mt-8 space-y-5">
          <div>
            <label className="block text-xs font-bold text-slate-400 uppercase tracking-widest mb-1.5">
              Email
            </label>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              className="w-full px-4 py-3 border border-slate-200 rounded-xl focus:ring-2 focus:ring-blue-500 focus:outline-none transition-all text-sm"
            />
          </div>

          <div>
            <label className="block text-xs font-bold text-slate-400 uppercase tracking-widest mb-1.5">
              Password
            </label>
            <input
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              className="w-full px-4 py-3 border border-slate-200 rounded-xl focus:ring-2 focus:ring-blue-500 focus:outline-none transition-all text-sm"
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-blue-600 hover:bg-blue-700 text-white py-3.5 rounded-xl font-bold transition shadow-lg disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? 'Logging in...' : 'Login'}
          </button>
        </form>

        <div className="my-6 flex items-center">
          <div className="grow border-t border-slate-100"></div>
          <span className="mx-3 text-slate-400 text-xs">OR</span>
          <div className="grow border-t border-slate-100"></div>
        </div>

        <p className="text-center text-slate-500 text-sm">
          Don’t have an account?{' '}
          <button
            onClick={() => onNavigate('signup')}
            className="text-blue-600 hover:underline font-bold"
          >
            Sign up
          </button>
        </p>
      </div>
    </div>
  );
};

export default Login;
