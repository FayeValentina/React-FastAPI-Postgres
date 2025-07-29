// import { defineConfig } from 'vite';
// import react from '@vitejs/plugin-react';

// // https://vitejs.dev/config/
// export default defineConfig({
//   plugins: [react()],
//   server: {
//     host: true,
//     port: Number(process.env.FRONTEND_PORT) || 3000,
//     proxy: {
//       '/api': {
//         // Check if running in local development mode
//         target: process.env.IS_BACKEND_LOCAL_DEV === 'true' 
//           ? `http://localhost:${process.env.BACKEND_PORT || 8000}`
//           : `http://backend:${process.env.BACKEND_PORT || 8000}`,
//         changeOrigin: true,
//         // Don't rewrite the path, keep /api prefix
//       }
//     }
//   }
// })
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: Number(process.env.FRONTEND_PORT) || 3000,
    proxy: {
      '/api': {
        // Check if running in local development mode
        target: process.env.IS_BACKEND_LOCAL_DEV === 'true' 
          ? `http://host.docker.internal:${process.env.BACKEND_PORT || 8000}`
          : `http://backend:${process.env.BACKEND_PORT || 8000}`,
        changeOrigin: true,
        // Don't rewrite the path, keep /api prefix
      }
    }
  }
})