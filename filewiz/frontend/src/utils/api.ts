import axios from 'axios';

const api = axios.create({
  baseURL: '', // Using relative paths which are proxied to localhost:3000 in dev
  withCredentials: true, // Enables cookie session tracking
  headers: {
    'Accept': 'application/json',
  }
});

export default api;
