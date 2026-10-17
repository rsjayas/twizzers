"""Calls from the API to the render service that are not 'make a video'."""
import os

import httpx


def delete_render_files(job_ids: list[str]) -> None:
    """Best-effort: asks the render service to delete the video and thumbnail files of these
    creations (local files and the copies in R2). A failure never blocks the caller; leftover
    files only cost storage."""
    url = os.getenv("RENDER_SERVICE_URL", "").rstrip("/")
    if not url or not job_ids:
        return
    secret = os.getenv("RENDER_SECRET", "")
    try:
        with httpx.Client(timeout=5) as client:
            for job_id in job_ids:
                client.delete(f"{url}/files/{job_id}", headers={"x-render-secret": secret})
    except httpx.HTTPError:
        pass
