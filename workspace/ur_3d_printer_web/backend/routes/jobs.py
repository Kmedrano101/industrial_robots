"""Print job history endpoints."""

from fastapi import APIRouter, HTTPException, Query

from backend import deps

router = APIRouter()


@router.get("/jobs")
async def list_jobs(limit: int = Query(50, ge=1, le=500)):
    store = deps.require_jobs()
    return {"jobs": store.list(limit), "current": store.current()}


@router.get("/jobs/{job_id}")
async def get_job(job_id: str):
    job = deps.require_jobs().get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.delete("/jobs/{job_id}")
async def delete_job(job_id: str):
    store = deps.require_jobs()
    if store.current() and store.current()["id"] == job_id:
        raise HTTPException(status_code=409, detail="Job is running")
    if not store.delete(job_id):
        raise HTTPException(status_code=404, detail="Job not found")
    return {"success": True}


@router.delete("/jobs")
async def clear_jobs():
    """Delete every finished job; the running one (if any) is kept."""
    return {"success": True, "deleted": deps.require_jobs().clear_finished()}
