import { defineConfig } from '@hey-api/openapi-ts';

// Generates the typed API client + React Query hooks + Zod schemas from the
// backend's OpenAPI contract. Run via `pnpm generate-api` (or `openapi-ts`
// directly) after refreshing ./openapi.json from the backend.
//
// input is a LOCAL file, not a live URL: keeps generation deterministic and
// offline-friendly (no backend needs to be running to regenerate the client).
export default defineConfig({
  input: './openapi.json',
  output: './src/lib/api/generated',
  plugins: [
    '@tanstack/react-query',
    'zod',
    {
      name: '@hey-api/sdk',
      validator: true,
    },
  ],
});
