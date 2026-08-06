"""Scenario 03: New FastAPI endpoint."""

from fastapi import FastAPI

app = FastAPI()


@app.get("/users/{user_id}")
async def get_user_endpoint(user_id: int):
    """Get user by ID."""
    return {"id": user_id}


@app.post("/users")
async def create_user_endpoint(name: str):
    """Create a new user."""
    return {"name": name}
