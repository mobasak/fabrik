/**
 * Health Check Endpoint
 * Required for Docker HEALTHCHECK and Coolify orchestration
 */
import { NextResponse } from 'next/server';

export async function GET() {
  // Basic health check - can be extended with database/redis checks
  const health = {
    status: 'ok',
    timestamp: new Date().toISOString(),
    uptime: process.uptime(),
  };

  return NextResponse.json(health, { status: 200 });
}

// Disable caching for health endpoint
export const dynamic = 'force-dynamic';
