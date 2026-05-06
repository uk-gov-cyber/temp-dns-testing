from uuid import uuid4
import time
from datetime import datetime, UTC
from typing import Literal
import asyncio
import socket

import aiodns
from fastapi import BackgroundTasks, FastAPI, HTTPException, Response
from pydantic import BaseModel, Field, field_validator

app = FastAPI()

# temp in-memory storage
JOBS: dict[str, dict] = {}


def default_record_types() -> list[str]:
    return ["A"]


class JobRequest(BaseModel):
    domains: list[str] = Field(min_length=1)
    record_types: list[str] = Field(default_factory=default_record_types, min_length=1)
    executor_mode: Literal["mock", "aiodns"] = "mock"

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


async def run_aiodns_queries(domains: list[str], record_types: list[str]) -> dict:
    resolver = aiodns.DNSResolver()
    results = []

    # Only support A records for now
    unsupported = [rt for rt in record_types if rt != "A"]
    if unsupported:
        raise ValueError(
            f"Only A record is supported in the first aiodns prototype, got: {unsupported}"
        )

    for domain in domains:
        try:
            answer = await resolver.gethostbyname(domain, socket.AF_INET)
            results.append(
                {
                    "domain": domain,
                    "record_type": "A",
                    "status": "success",
                    "answers": answer.addresses,
                }
            )
        except Exception as exc:
            results.append(
                {
                    "domain": domain,
                    "record_type": "A",
                    "status": "error",
                    "answers": [],
                    "error": str(exc),
                }
            )

    return {
        "message": "Task finished successfully",
        "domain_count": len(domains),
        "records": results,
    }


def run_mock_queries(domains: list[str], record_types: list[str]) -> dict:
    return {
        "message": "Task finished successfully",
        "domain_count": len(domains),
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


def execute_queries(
    domains: list[str], record_types: list[str], executor_mode: str
) -> dict:
    if executor_mode == "mock":
        return run_mock_queries(domains, record_types)

    if executor_mode == "aiodns":
        return asyncio.run(run_aiodns_queries(domains, record_types))

    raise ValueError(f"Unsupported executor_mode: {executor_mode}")


def run_long_task(job_id: str, payload: dict) -> None:
    try:
        started = time.perf_counter()
        JOBS[job_id]["status"] = "running"

        domains = payload.get("domains", [])
        record_types = payload.get("record_types", ["A"])
        executor_mode = payload.get("executor_mode", "mock")

        result = execute_queries(domains, record_types, executor_mode)

        JOBS[job_id]["status"] = "completed"
        JOBS[job_id]["completed_at"] = datetime.now(UTC).isoformat()
        JOBS[job_id]["duration_seconds"] = round(time.perf_counter() - started, 3)
        JOBS[job_id]["result"] = result

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
        "executor_mode": payload.executor_mode,
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
            "record_types_requested": job["record_types_requested"],
            "executor_mode": job["executor_mode"],
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
            "record_types_requested": job["record_types_requested"],
            "executor_mode": job["executor_mode"],
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
        "executor_mode": job["executor_mode"],
        "created_at": job["created_at"],
        "completed_at": job["completed_at"],
        "duration_seconds": job["duration_seconds"],
        "message": "Job completed successfully",
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
            "record_types_requested": job["record_types_requested"],
            "message": "Results not ready yet",
        }

    return {
        "job_id": job_id,
        "status": job["status"],
        "results_url": f"/jobs/{job_id}/results",
        "record_types_requested": job["record_types_requested"],
        "created_at": job["created_at"],
        "completed_at": job["completed_at"],
        "duration_seconds": job["duration_seconds"],
        "result": job["result"],
    }
