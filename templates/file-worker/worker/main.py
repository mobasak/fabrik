"""
File Worker - Job processor for file operations.

Polls Supabase for pending jobs and processes them:
- transcribe: Audio transcription (placeholder)
- ocr: OCR text extraction from images/PDFs
- extract_text: PDF text extraction
"""

import os
import signal
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import boto3
import structlog
from supabase import Client, create_client

# Configure logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

log = structlog.get_logger()

# Config
WORKER_ID = os.getenv("WORKER_ID", "worker-1")
JOB_TYPES = os.getenv("JOB_TYPES", "transcribe,ocr,extract_text").split(",")
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "5"))
MAX_CONCURRENT = int(os.getenv("MAX_CONCURRENT_JOBS", "2"))
MAX_PROCESSING_TIME = int(os.getenv("MAX_PROCESSING_TIME", "3600"))

# Clients
supabase: Client = create_client(
    os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"]
)

s3 = boto3.client(
    "s3",
    endpoint_url=os.environ["R2_ENDPOINT"],
    aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
    aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
    region_name="auto",
)

R2_BUCKET = os.environ["R2_BUCKET"]

# Shutdown flag
shutdown_requested = False


def signal_handler(signum, frame):
    global shutdown_requested
    log.info("shutdown_requested", signal=signum)
    shutdown_requested = True


signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)


def download_file(r2_key: str, local_path: Path) -> None:
    """Download file from R2 to local path."""
    s3.download_file(R2_BUCKET, r2_key, str(local_path))


def upload_file(
    local_path: Path, r2_key: str, content_type: str = "application/octet-stream"
) -> None:
    """Upload file from local path to R2."""
    s3.upload_file(str(local_path), R2_BUCKET, r2_key, ExtraArgs={"ContentType": content_type})


def claim_job() -> dict | None:
    """Claim next pending job using database function."""
    result = supabase.rpc(
        "claim_next_job", {"p_job_types": JOB_TYPES, "p_worker_id": WORKER_ID}
    ).execute()

    if result.data:
        return result.data
    return None


def complete_job(job_id: str, success: bool, result_data: dict = None, error_message: str = None):
    """Mark job as completed or failed."""
    update = {
        "status": "completed" if success else "failed",
        "completed_at": "now()",
    }

    if result_data:
        update["result_data"] = result_data
    if error_message:
        update["error_message"] = error_message

    supabase.table("processing_jobs").update(update).eq("id", job_id).execute()


def get_file_info(file_id: str) -> dict | None:
    """Get file metadata."""
    result = supabase.table("files").select("*").eq("id", file_id).single().execute()
    return result.data


def create_derivative(
    file_id: str,
    derivative_type: str,
    r2_key: str,
    content_type: str,
    size_bytes: int,
    metadata: dict = None,
):
    """Create derivative record."""
    supabase.table("file_derivatives").insert(
        {
            "file_id": file_id,
            "derivative_type": derivative_type,
            "r2_key": r2_key,
            "content_type": content_type,
            "size_bytes": size_bytes,
            "metadata": metadata or {},
        }
    ).execute()


def process_extract_text(job: dict, file_info: dict) -> dict:
    """Extract text from PDF."""
    from pypdf import PdfReader

    with tempfile.TemporaryDirectory() as tmpdir:
        local_path = Path(tmpdir) / "input.pdf"
        output_path = Path(tmpdir) / "extracted.txt"

        # Download
        download_file(file_info["r2_key"], local_path)

        # Extract text
        reader = PdfReader(local_path)
        text_parts = []
        for page in reader.pages:
            text_parts.append(page.extract_text() or "")

        full_text = "\n\n".join(text_parts)
        output_path.write_text(full_text, encoding="utf-8")

        # Upload derivative
        derivative_key = f"derivatives/{file_info['tenant_id']}/{file_info['id']}/extracted.txt"
        upload_file(output_path, derivative_key, "text/plain")

        # Create derivative record
        create_derivative(
            file_id=file_info["id"],
            derivative_type="extracted_text",
            r2_key=derivative_key,
            content_type="text/plain",
            size_bytes=len(full_text.encode("utf-8")),
            metadata={"page_count": len(reader.pages), "char_count": len(full_text)},
        )

        return {
            "page_count": len(reader.pages),
            "char_count": len(full_text),
            "derivative_key": derivative_key,
        }


def process_ocr(job: dict, file_info: dict) -> dict:
    """OCR text extraction from images or PDFs."""
    import pytesseract
    from pdf2image import convert_from_path
    from PIL import Image

    with tempfile.TemporaryDirectory() as tmpdir:
        local_path = Path(tmpdir) / "input"
        output_path = Path(tmpdir) / "ocr.txt"

        # Download
        download_file(file_info["r2_key"], local_path)

        text_parts = []

        if file_info["content_type"] == "application/pdf":
            # Convert PDF pages to images
            images = convert_from_path(local_path)
            for i, img in enumerate(images):
                text = pytesseract.image_to_string(img)
                text_parts.append(f"--- Page {i+1} ---\n{text}")
        else:
            # Direct image OCR
            img = Image.open(local_path)
            text_parts.append(pytesseract.image_to_string(img))

        full_text = "\n\n".join(text_parts)
        output_path.write_text(full_text, encoding="utf-8")

        # Upload derivative
        derivative_key = f"derivatives/{file_info['tenant_id']}/{file_info['id']}/ocr.txt"
        upload_file(output_path, derivative_key, "text/plain")

        # Create derivative record
        create_derivative(
            file_id=file_info["id"],
            derivative_type="ocr_text",
            r2_key=derivative_key,
            content_type="text/plain",
            size_bytes=len(full_text.encode("utf-8")),
            metadata={"char_count": len(full_text)},
        )

        return {"char_count": len(full_text), "derivative_key": derivative_key}


def process_transcribe(job: dict, file_info: dict) -> dict:
    """Audio transcription (placeholder - integrate with Soniox/Whisper)."""
    # TODO: Integrate with actual transcription service
    # For now, create a placeholder

    log.warning("transcribe_not_implemented", file_id=file_info["id"])

    return {"status": "not_implemented", "message": "Transcription service not yet configured"}


def process_job(job: dict) -> None:
    """Process a single job."""
    job_id = job["id"]
    job_type = job["job_type"]
    file_id = job["file_id"]

    log.info("processing_job", job_id=job_id, job_type=job_type, file_id=file_id)

    try:
        # Get file info
        file_info = get_file_info(file_id)
        if not file_info:
            raise ValueError(f"File not found: {file_id}")

        # Process based on type
        if job_type == "extract_text":
            result = process_extract_text(job, file_info)
        elif job_type == "ocr":
            result = process_ocr(job, file_info)
        elif job_type == "transcribe":
            result = process_transcribe(job, file_info)
        else:
            raise ValueError(f"Unknown job type: {job_type}")

        complete_job(job_id, success=True, result_data=result)
        log.info("job_completed", job_id=job_id, result=result)

    except Exception as e:
        log.error("job_failed", job_id=job_id, error=str(e))
        complete_job(job_id, success=False, error_message=str(e))


def main():
    """Main worker loop."""
    log.info("worker_starting", worker_id=WORKER_ID, job_types=JOB_TYPES)

    with ThreadPoolExecutor(max_workers=MAX_CONCURRENT) as executor:
        futures = {}

        while not shutdown_requested:
            # Clean up completed futures
            done = [f for f in futures if f.done()]
            for f in done:
                try:
                    f.result()
                except Exception as e:
                    log.error("future_error", error=str(e))
                del futures[f]

            # Claim new jobs if we have capacity
            while len(futures) < MAX_CONCURRENT and not shutdown_requested:
                job = claim_job()
                if not job:
                    break

                future = executor.submit(process_job, job)
                futures[future] = job["id"]

            # Sleep before next poll
            time.sleep(POLL_INTERVAL)

        # Wait for running jobs on shutdown
        log.info("waiting_for_jobs", count=len(futures))
        for f in as_completed(futures, timeout=60):
            try:
                f.result()
            except Exception as e:
                log.error("shutdown_job_error", error=str(e))

    log.info("worker_stopped")


if __name__ == "__main__":
    main()
