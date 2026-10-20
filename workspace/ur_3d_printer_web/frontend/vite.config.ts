/// <reference types="vitest" />
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { VitePWA } from 'vite-plugin-pwa';
import path from 'path';

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: ['favicon.ico', 'tidop_logo.png', 'zamora_futurelab.svg'],
      manifest: {
        name: 'Robot 3D Printer',
        short_name: 'Robot 3D Printer',
        description: 'Web interface for Universal Robots 3D Printer control',
        theme_color: '#0f172a',
        background_color: '#0f172a',
        display: 'standalone',
        orientation: 'any',
        start_url: '/',
        scope: '/',
        categories: ['productivity', 'utilities'],
        icons: [
          {
            src: 'pwa-192x192.png',
            sizes: '192x192',
            type: 'image/png',
          },
          {
            src: 'pwa-512x512.png',
            sizes: '512x512',
            type: 'image/png',
          },
          {
            src: 'pwa-maskable-192x192.png',
            sizes: '192x192',
            type: 'image/png',
            purpose: 'maskable',
          },
          {
            src: 'pwa-maskable-512x512.png',
            sizes: '512x512',
            type: 'image/png',
            purpose: 'maskable',
          },
        ],
      },
      workbox: {
        globPatterns: ['**/*.{js,css,html,ico,png,svg,woff2}'],
        // The robot meshes are large; let the precache take them.
        maximumFileSizeToCacheInBytes: 6 * 1024 * 1024,
        // The API is never served from cache. This is a machine-control
        // UI: a cached /api/robot/status or /api/state replayed while the
        // backend is down would show a robot state that is not true, which
        // is worse than an honest "no backend". It used to be NetworkFirst
        // with a 5-minute cache.
        navigateFallbackDenylist: [/^\/api\//],
        runtimeCaching: [
          {
            urlPattern: /^\/api\//,
            handler: 'NetworkOnly',
          },
        ],
      },
    }),
  ],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8090',
        ws: true,
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
    // The `three` chunk is ~1 MB minified; that is the library itself, not
    // a bundling mistake, and it is loaded lazily. Warn only above it.
    chunkSizeWarningLimit: 1100,
    rollupOptions: {
      output: {
        // three.js and the URDF loader are ~two thirds of the bundle and only
        // the 3D views need them; the React/i18n runtime changes rarely.
        // Separate chunks let the browser keep each cached across releases
        // that only touch application code, and let the Robot page and
        // the viewer load on demand (see AppShell).
        //
        // Function form, matched on the module path: the object form pins
        // only a package's entry module, so `react/jsx-runtime` and Vite's
        // own preload helper ended up in whichever chunk first imported
        // them (`three`), and the entry chunk then imported `three`
        // statically — which silently undid the lazy loading.
        manualChunks(id) {
          // Vite's own preload helper is a virtual module (no node_modules
          // in its id). Left unassigned it lands in whichever chunk Rollup
          // visits first — `three` — and the entry imports it from there.
          if (id.includes('vite/preload-helper')) return 'vendor';
          if (!id.includes('node_modules')) return undefined;
          if (/[\\/]node_modules[\\/](three|@react-three|urdf-loader|three-stdlib)[\\/]/.test(id)) {
            return 'three';
          }
          return 'vendor';
        },
      },
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
    css: false,
  },
});
