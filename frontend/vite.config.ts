
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: Number(process.env.FRONTEND_PORT) || 3000,
    // 删除所有 proxy 配置，nginx 处理代理
    hmr: {
      // 支持 nginx 代理的 HMR 配置
      clientPort: 80, // nginx 监听的端口
    }
  }
});
