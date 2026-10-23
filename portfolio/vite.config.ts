import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { publicAssets } from './scripts/public-assets.ts';
import sourceFiles from './public-source-files.json' with { type: 'json' };

const root = fileURLToPath(new URL('../', import.meta.url));
export default defineConfig({
  base: '/',
  plugins: [
    react(),
    tailwindcss(),
    {
      name: 'reviewed-public-assets',
      configureServer(server) {
        const assets = publicAssets(root, sourceFiles);
        assets.set('data/evidence.json', readFileSync(new URL('./src/data/evidence.json', import.meta.url), 'utf8'));
        server.middlewares.use((req, res, next) => {
          const key = new URL(req.url ?? '/', 'http://127.0.0.1').pathname.slice(1);
          const body = assets.get(key);
          if (body === undefined) return next();
          res.setHeader('Content-Type', key.endsWith('.html') ? 'text/html; charset=utf-8' : key.endsWith('.json') ? 'application/json' : 'text/plain; charset=utf-8');
          res.end(body);
        });
      },
      generateBundle(_options, bundle) {
        for (const [fileName, source] of publicAssets(root, sourceFiles))
          this.emitFile({ type: 'asset', fileName, source });
        this.emitFile({
          type: 'asset', fileName: 'data/evidence.json',
          source: readFileSync(new URL('./src/data/evidence.json', import.meta.url), 'utf8'),
        });
        const covered = new Set(['react', 'react-dom', 'scheduler', 'lucide-react', 'vite', 'tailwindcss']);
        const bundled = new Set<string>();
        for (const chunk of Object.values(bundle)) {
          if (chunk.type !== 'chunk') continue;
          for (const id of Object.keys(chunk.modules)) {
            const match = /node_modules\/((?:@[^/]+\/)?[^/]+)/.exec(id);
            if (match) {
              if (!covered.has(match[1])) throw new Error('Unreviewed bundled dependency: ' + match[1]);
              bundled.add(match[1]);
            }
          }
        }
        this.emitFile({ type: 'asset', fileName: 'data/bundle-packages.json', source: JSON.stringify({ bundledPackages: [...bundled].sort(), helperNotices: ['vite', 'tailwindcss'] }, null, 2) + '\n' });
      },
    },
  ],
  test: {
    environment: 'jsdom', include: ['src/**/*.test.{ts,tsx}'],
    setupFiles: ['./src/test-setup.ts'], restoreMocks: true,
  },
});
