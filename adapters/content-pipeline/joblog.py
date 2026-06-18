"""Append a job-run record to Supabase `job_runs` — observability for the launchd jobs
(capture / discover), surfaced in Megaphone. Best-effort: never fails the job it logs.

    python joblog.py <job> <status> <started_at_iso> [summary] [exit_code]
"""
import datetime as dt
import socket
import sys

import store  # reuse the content-pipeline Supabase client


def main() -> None:
    if len(sys.argv) < 4:
        return
    job, status, started = sys.argv[1], sys.argv[2], sys.argv[3]
    summary = sys.argv[4] if len(sys.argv) > 4 else None
    exit_code = None
    if len(sys.argv) > 5:
        try:
            exit_code = int(sys.argv[5])
        except ValueError:
            pass
    row = {
        "job": job,
        "status": status,
        "started_at": started or None,
        "finished_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "exit_code": exit_code,
        "summary": ((summary or "").strip()[:500]) or None,
        "host": socket.gethostname(),
    }
    try:
        store._client().table("job_runs").insert(row).execute()
        print(f"[joblog] {job} {status}")
    except Exception as e:  # table missing / network — log to stderr, don't fail the job
        print(f"[joblog] insert skipped: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
