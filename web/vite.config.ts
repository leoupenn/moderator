import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    // Bind all interfaces so http://<LAN-IP>:5173 works from other devices
    host: "0.0.0.0",
    port: 5173,
    strictPort: true,
    // Allow opening the dev server via LAN IP (e.g. http://192.168.x.x:5173)
    allowedHosts: true,
    proxy: {
      "/socket.io": {
        target: "http://127.0.0.1:3847",
        ws: true,
        changeOrigin: true,
      },
    },
  },
});
