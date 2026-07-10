// The Obytes axios client has been replaced by the generated `@hey-api/openapi-ts`
// client/SDK (see ../../../openapi-ts.config.ts). Run the generator against
// ./openapi.json to populate ./generated with a typed client, React Query
// hooks, and Zod validators — nothing here should hand-roll HTTP calls.
import { client } from './generated/client.gen';

// Point the generated SDK at the backend. EXPO_PUBLIC_API_URL is required (see
// .env.example) — without it the SDK would issue relative requests that fail
// on-device. Set once at module load so every generated call/hook is configured.
client.setConfig({ baseUrl: process.env.EXPO_PUBLIC_API_URL });

export { client } from './generated/client.gen';
export * from './generated';
