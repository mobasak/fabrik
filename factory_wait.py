#!/usr/bin/env python3
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import time

JOBS_DIR = pathlib.Path(os.getenv("FACTORY_JOBS_DIR", ".factory_jobs"))
JOBS_DIR.mkdir(parents=True, exist_ok=True)


def load_job(job_id: str):
    path = JOBS_DIR / f"{job_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"Job {job_id} not found at {path}")
    return path, json.loads(path.read_text(encoding="utf-8"))


def save_job(path: pathlib.Path, job: dict):
    job["updated_at"] = time.time()
    path.write_text(json.dumps(job, indent=2), encoding="utf-8")


def pick_job_id_from_args_or_latest():
    # If user passed job_id as first argument
    if len(sys.argv) > 1:
        return sys.argv[1]
    # Otherwise, fall back to "latest job"
    latest = JOBS_DIR / "latest_job.txt"
    if latest.exists():
        return latest.read_text(encoding="utf-8").strip()
    return None


def build_summary(job: dict) -> dict:
    """
    Build a small summary JSON from the job, including a parsed Factory report if possible.
    """
    # Try to extract a human-readable report from factory_stdout
    report = None
    try:
        stdout_text = job.get("factory_stdout") or ""
        # Factory’s droid exec result JSON is typically at the end after some terminal noise
        candidate = stdout_text.split("\x07")[-1].strip()  # split on BEL, take last segment
        inner = json.loads(candidate)
        report = inner.get("result")
    except Exception:
        report = None  # best-effort only

    summary = {
        "job_id": job["job_id"],
        "status": job["status"],
        "artifacts": job.get("artifacts", []),
        "error": job.get("error"),
        "has_report": bool(report),
        "report": report,
    }
    return summary


def main():
    job_id = pick_job_id_from_args_or_latest()
    if not job_id:
        print(
            json.dumps(
                {"status": "error", "message": "No job_id provided and no latest_job.txt found"}
            )
        )
        sys.exit(1)

    try:
        job_path, job = load_job(job_id)
    except FileNotFoundError as e:
        print(json.dumps({"status": "error", "message": str(e)}))
        sys.exit(1)

    # If already finished, just return a clean summary
    if job["status"] in ("completed", "failed"):
        summary = build_summary(job)
        print(json.dumps(summary))
        sys.exit(0 if job["status"] == "completed" else 1)

    # MVP: run the job now using droid
    with tempfile.NamedTemporaryFile("w+", delete=False, encoding="utf-8") as spec_file:
        spec_file.write(job["spec"])
        spec_file.flush()
        spec_path = spec_file.name

    cmd = [
        "droid",
        "exec",
        "-f",
        spec_path,
        "--auto",
        os.getenv("FACTORY_AUTO_LEVEL", "medium"),
        "-o",
        "json",
    ]

    proc = subprocess.run(cmd, text=True, capture_output=True)

    job["factory_stdout"] = proc.stdout
    job["factory_stderr"] = proc.stderr

    if proc.returncode == 0:
        job["status"] = "completed"
        job["artifacts"] = job.get("artifacts", [])
        err = None
    else:
        job["status"] = "failed"
        err = f"Factory CLI exited with code {proc.returncode}"

    job["error"] = err
    save_job(job_path, job)

    # Build and print summary (same shape as for already-completed jobs)
    summary = build_summary(job)
    print(json.dumps(summary))
    sys.exit(0 if job["status"] == "completed" else 1)


if __name__ == "__main__":
    main()
