#!/usr/bin/env python3
import json
import os
import pathlib
import sys
import time
import uuid

# Where to store job files
JOBS_DIR = pathlib.Path(os.getenv("FACTORY_JOBS_DIR", ".factory_jobs"))
JOBS_DIR.mkdir(parents=True, exist_ok=True)


def main():
    # 1) Read the spec that Traycer passes via env
    spec = os.environ.get("TRAYCER_PROMPT", "").strip()
    if not spec:
        print(
            json.dumps(
                {"status": "error", "message": "TRAYCER_PROMPT was empty; nothing to submit"}
            )
        )
        sys.exit(1)

    # 2) Create a new job_id and file path
    job_id = uuid.uuid4().hex[:8]  # short random id
    job_path = JOBS_DIR / f"{job_id}.json"
    now = time.time()

    # 3) Build the job object
    job = {
        "job_id": job_id,
        "status": "queued",  # not run yet
        "spec": spec,  # instructions for Factory/droid
        "artifacts": [],  # you can fill later
        "factory_stdout": None,
        "factory_stderr": None,
        "created_at": now,
        "updated_at": now,
        "error": None,
    }

    # 4) Save job to disk
    job_path.write_text(json.dumps(job, indent=2), encoding="utf-8")

    # 5) Track latest job_id
    (JOBS_DIR / "latest_job.txt").write_text(job_id, encoding="utf-8")

    # 6) Print confirmation JSON for Traycer
    print(json.dumps({"status": "submitted", "job_id": job_id}))
    sys.exit(0)


if __name__ == "__main__":
    main()
