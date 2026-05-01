from uuid import uuid4
import time
from datetime import datetime, UTC

from fastapi import BackgroundTasks, FastAPI, HTTPException, Response
from pydantic import BaseModel, Field, field_validator

app = FastAPI()

# temp in-memory db
JOBS: dict[str, dict] = {}


def default_record_types() -> list[str]:
    return ["A"]


class JobRequest(BaseModel):
    domains: list[str] = Field(min_length=1)
    record_types: list[str] = Field(default_factory=default_record_types, min_length=1)

    @field_validator("domains")
    def clean_domains(cls, value: list[str]) -> list[str]:
        cleaned = []

        for domain in value:
            stripped = domain.strip()
            if stripped:
                cleaned.append(stripped)

        if not cleaned:
            raise ValueError("domains must contain at least one non-empty value")

        return cleaned

    @field_validator("record_types")
    def clean_record_types(cls, value: list[str]) -> list[str]:
        cleaned = []

        for record_type in value:
            stripped = record_type.strip().upper()
            if stripped:
                cleaned.append(stripped)

        if not cleaned:
            raise ValueError("record_types must contain at least one non-empty value")

        return cleaned


# For now it just sleeps and returns a fake result.
def run_long_task(job_id: str, payload: dict) -> None:
    try:
        started = time.perf_counter()
        JOBS[job_id]["status"] = "running"

        # Placeholder for long-running work
        time.sleep(10)

        domains = payload.get("domains", [])
        record_types = payload.get("record_types", ["A"])

        JOBS[job_id]["status"] = "completed"
        JOBS[job_id]["completed_at"] = datetime.now(UTC).isoformat()
        JOBS[job_id]["duration_seconds"] = round(time.perf_counter() - started, 3)
        JOBS[job_id]["result"] = {
            "message": "Task finished successfully",
            "domain_count": len(domains),
            "record_types_requested": record_types,
            "records": [
                {
                    "domain": domain,
                    "record_type": record_type,
                    "status": "success",
                    "answers": ["127.0.0.1"],
                }
                for domain in domains
                for record_type in record_types
            ],
        }

    except Exception as exc:
        JOBS[job_id]["status"] = "failed"
        JOBS[job_id]["completed_at"] = datetime.now(UTC).isoformat()
        JOBS[job_id]["duration_seconds"] = round(time.perf_counter() - started, 3)
        JOBS[job_id]["error"] = str(exc)


@app.get("/")
async def root():
    return {"message": "dns test"}


@app.get("/health")
async def health():
    return {"status": "ok"}


# Submits a new job.
# The request is accepted immediately, the work runs in the background,
# and the client can poll the status or results URLs.
@app.post("/jobs", status_code=202)
async def create_job(payload: JobRequest, background_tasks: BackgroundTasks):
    job_id = str(uuid4())

    JOBS[job_id] = {
        "status": "pending",
        "result": None,
        "error": None,
        "submitted_domains_count": len(payload.domains),
        "record_types_requested": payload.record_types,
        "created_at": datetime.now(UTC).isoformat(),
        "completed_at": None,
        "duration_seconds": None,
    }

    background_tasks.add_task(run_long_task, job_id, payload.model_dump())

    return {
        "job_id": job_id,
        "status": "pending",
        "status_url": f"/jobs/{job_id}",
        "results_url": f"/jobs/{job_id}/results",
    }


@app.get("/jobs/{job_id}")
async def get_job(job_id: str):
    job = JOBS.get(job_id)

    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    status_url = f"/jobs/{job_id}"
    results_url = f"/jobs/{job_id}/results"

    if job["status"] in ["pending", "running"]:
        return {
            "job_id": job_id,
            "status": job["status"],
            "status_url": status_url,
            "results_url": results_url,
            "submitted_domains_count": job["submitted_domains_count"],
            "created_at": job["created_at"],
            "completed_at": job["completed_at"],
            "message": "Job still in progress",
        }

    if job["status"] == "failed":
        return {
            "job_id": job_id,
            "status": job["status"],
            "status_url": status_url,
            "results_url": results_url,
            "submitted_domains_count": job["submitted_domains_count"],
            "created_at": job["created_at"],
            "completed_at": job["completed_at"],
            "duration_seconds": job["duration_seconds"],
            "error": job["error"],
        }

    return {
        "job_id": job_id,
        "status": job["status"],
        "status_url": status_url,
        "results_url": results_url,
        "submitted_domains_count": job["submitted_domains_count"],
        "record_types_requested": job["record_types_requested"],
        "created_at": job["created_at"],
        "completed_at": job["completed_at"],
        "duration_seconds": job["duration_seconds"],
        "result": job["result"],
    }


@app.get("/jobs/{job_id}/results")
async def get_job_results(job_id: str, response: Response):
    job = JOBS.get(job_id)

    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    if job["status"] != "completed":
        response.status_code = 202
        return {
            "job_id": job_id,
            "status": job["status"],
            "results_url": f"/jobs/{job_id}/results",
            "message": "Results not ready yet",
        }

    return {
        "job_id": job_id,
        "status": job["status"],
        "results_url": f"/jobs/{job_id}/results",
        "created_at": job["created_at"],
        "completed_at": job["completed_at"],
        "duration_seconds": job["duration_seconds"],
        "result": job["result"],
    }
