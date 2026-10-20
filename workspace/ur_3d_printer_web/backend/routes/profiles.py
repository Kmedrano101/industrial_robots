"""Material / process profile endpoints."""

from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend import deps

router = APIRouter()


class ProfileIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    settings: dict[str, Any]
    id: Optional[str] = Field(default=None, description="Update an existing user profile")


@router.get("/profiles")
async def list_profiles():
    return {"profiles": deps.require_profiles().list()}


@router.put("/profiles")
async def save_profile(body: ProfileIn):
    store = deps.require_profiles()
    if body.id:
        existing = store.get(body.id)
        if existing is None:
            raise HTTPException(status_code=404, detail="Profile not found")
        if existing.get("builtin"):
            raise HTTPException(status_code=403, detail="Built-in profiles are read-only")
    return store.upsert(body.name, body.settings, body.id)


@router.delete("/profiles/{profile_id}")
async def delete_profile(profile_id: str):
    store = deps.require_profiles()
    existing = store.get(profile_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    if existing.get("builtin"):
        raise HTTPException(status_code=403, detail="Built-in profiles are read-only")
    store.delete(profile_id)
    return {"success": True}
