import axios from 'axios';
import { setupInterceptors } from './interceptors';

const api = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json',
  },
});

// Setup interceptors for automatic token management
setupInterceptors(api);

export default api; 