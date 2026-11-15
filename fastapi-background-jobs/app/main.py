import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, EmailStr
from redis import Redis
from redis.exceptions import RedisError
from rq import Queue, Retry
from rq.exceptions import NoSuchJobError
from rq.job import Job

from app.jobs.email_jobs import send_welcome_email

# Load environment variables
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

app = FastAPI(
    title="FastAPI + Redis + RQ Background Jobs",
    description="Asynchronous email worker queue demonstration using Redis and RQ",
    version="1.0.0"
)

# Connect to Redis using synchronous client required by RQ
redis_connection = Redis.from_url(
    REDIS_URL,
    decode_responses=False,
    socket_connect_timeout=5,
    socket_timeout=5
)

# Initialize RQ Queue
email_queue = Queue("emails", connection=redis_connection)


class RegistrationRequest(BaseModel):
    email: EmailStr


class RegistrationResponse(BaseModel):
    message: str
    job_id: str
    email_status: str


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    result: dict | None = None
    enqueued_at: str | None = None
    ended_at: str | None = None


@app.get("/")
def root():
    return {
        "message": "FastAPI + Redis + RQ Background Jobs API",
        "docs_url": "/docs",
        "queue": "emails"
    }


@app.get("/health")
def health():
    try:
        redis_connection.ping()
        return {"status": "ok", "redis": "connected"}
    except RedisError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Redis connection failed: {str(e)}"
        )


@app.post("/register", status_code=status.HTTP_202_ACCEPTED, response_model=RegistrationResponse)
def register(payload: RegistrationRequest):
    """
    Submits a welcome email job to Redis without blocking the HTTP request.
    Configured with 3 retries with backoff [10s, 30s, 60s].
    """
    try:
        job = email_queue.enqueue(
            send_welcome_email,
            payload.email,
            job_timeout=60,
            retry=Retry(max=3, interval=[10, 30, 60])
        )
    except RedisError as err:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Could not enqueue background job: {err}"
        )

    return {
        "message": "Registration successful",
        "job_id": job.id,
        "email_status": "queued"
    }


@app.get("/jobs/{job_id}", response_model=JobStatusResponse)
def get_job_status(job_id: str):
    """
    Retrieves the current execution status and result of a background job.
    """
    try:
        job = Job.fetch(job_id, connection=redis_connection)
        job_status = job.get_status()
        status_str = job_status.value if hasattr(job_status, "value") else str(job_status)
        return {
            "job_id": job.id,
            "status": status_str,
            "result": job.result if job.is_finished else None,
            "enqueued_at": str(job.enqueued_at) if job.enqueued_at else None,
            "ended_at": str(job.ended_at) if job.ended_at else None
        }
    except NoSuchJobError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )
