"""
FastAPI Application - Python API Template
Includes mandatory health endpoint and tenant isolation example
"""
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime
from typing import Optional
import os

app = FastAPI(
    title="Fabrik Python API",
    description="FastAPI microservice template with tenant isolation",
    version="1.0.0",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Pydantic models
class HealthResponse(BaseModel):
    status: str
    timestamp: str
    environment: str
    uptime: Optional[float] = None


class StatusResponse(BaseModel):
    service: str
    version: str
    timestamp: str


class ResourceResponse(BaseModel):
    id: str
    tenant_id: str
    name: str
    created_at: str


# Mandatory Health Check for Fabrik Factory
@app.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint for Docker HEALTHCHECK and Coolify orchestration.
    In production, this should test actual dependencies (database, redis, etc.)
    """
    return HealthResponse(
        status="ok",
        timestamp=datetime.utcnow().isoformat(),
        environment=os.getenv("ENVIRONMENT", "development"),
    )


# API Status endpoint
@app.get("/api/v1/status", response_model=StatusResponse)
async def get_status():
    """API service status"""
    return StatusResponse(
        service="python-api",
        version="1.0.0",
        timestamp=datetime.utcnow().isoformat(),
    )


# Example: Dependency for tenant isolation
async def get_current_tenant(
    # In production, extract from JWT token
    tenant_header: Optional[str] = None,
) -> str:
    """
    Dependency to extract and validate current tenant ID.
    In production, this would:
    1. Validate JWT token
    2. Extract tenant_id from token claims
    3. Verify tenant is active
    """
    if not tenant_header:
        raise HTTPException(
            status_code=401,
            detail="Tenant authentication required",
        )
    return tenant_header


# Example: Tenant-isolated resource endpoint
@app.get("/api/v1/resources/{resource_id}", response_model=ResourceResponse)
async def get_resource(
    resource_id: str,
    tenant_id: str = Depends(get_current_tenant),
):
    """
    Example endpoint demonstrating tenant isolation.
    
    One-Test Rule: This endpoint MUST return 404 if resource_id belongs
    to a different tenant than the authenticated tenant_id.
    """
    # In production, query database with BOTH filters:
    # - resource.id == resource_id
    # - resource.tenant_id == tenant_id  ← CRITICAL for isolation
    
    # Example response (in production, this comes from database)
    # If resource not found OR tenant mismatch, return 404
    if resource_id != "example-resource-123":
        raise HTTPException(status_code=404, detail="Resource not found")
    
    return ResourceResponse(
        id=resource_id,
        tenant_id=tenant_id,
        name="Example Resource",
        created_at=datetime.utcnow().isoformat(),
    )


# Error handler for unhandled exceptions
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """
    Global exception handler to prevent traceback leakage in production.
    In development, you might want to return the full traceback.
    """
    environment = os.getenv("ENVIRONMENT", "development")
    
    if environment == "production":
        # Don't expose internal errors in production
        return {
            "detail": "Internal server error",
            "status_code": 500,
        }
    else:
        # In development, return full error for debugging
        import traceback
        return {
            "detail": str(exc),
            "traceback": traceback.format_exc(),
            "status_code": 500,
        }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
