"""Start the paired Windows job using this project's GitLab job token."""
from __future__ import annotations

import json
from datetime import datetime
import re
import urllib.parse
import urllib.request

ENDPOINT = "https://gitlab.saffti.jp/api/v4/projects/38/trigger/pipeline"
JOBS = "https://gitlab.saffti.jp/api/v4/projects/38/pipelines/{}/jobs?per_page=100"


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs):
        return None


def trigger_worker(token: str, ref: str, parent_pipeline: str, source_sha: str, session: str, mode: str,
                   build_seconds: int, *, opener=None) -> int:
    """Send only nonsecret routing variables; the token stays in the form body."""
    if (not token or not ref or any(c in ref for c in "\r\n\0")
            or not re.fullmatch(r"[0-9]{1,20}", parent_pipeline) or not re.fullmatch(r"[0-9]{1,20}", session)
            or mode not in ("public", "transport")
            or type(build_seconds) is not int or not 0 < build_seconds <= 10800
            or not re.fullmatch(r"[0-9a-f]{40}", source_sha)):
        raise ValueError("invalid paired pipeline identity")
    values = {"token": token, "ref": ref,
              "variables[IDT_PAIR_MODE]": mode,
              "variables[IDT_PAIR_PARENT_PIPELINE]": parent_pipeline,
              "variables[IDT_PAIR_SESSION]": session,
              "variables[IDT_PAIR_BUILD_SECONDS]": str(build_seconds),
              "variables[IDT_PAIR_PARENT_SHA]": source_sha}
    request = urllib.request.Request(ENDPOINT, data=urllib.parse.urlencode(values).encode("ascii"), method="POST")
    client = opener or urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    try:
        with client.open(request, timeout=15) as response:
            data = response.read(65537)
        if len(data) > 65536:
            raise ValueError
        result = json.loads(data)
        if (not isinstance(result, dict) or type(result.get("id")) is not int or result["id"] <= 0
                or result.get("sha") != source_sha or result.get("ref") != ref
                or result.get("source") != "pipeline"):
            raise ValueError
        return result["id"]
    except Exception:
        # Do not retry: a timed-out POST may already have started the job.
        raise RuntimeError("paired Windows pipeline could not be confirmed") from None


def worker_status(token: str, pipeline: int, source_sha: str, mode: str, *, opener=None) -> dict:
    """Read the one expected child job without exposing its job token."""
    if (not token or type(pipeline) is not int or pipeline <= 0
            or not re.fullmatch(r"[0-9a-f]{40}", source_sha) or mode not in ("public", "transport")):
        raise ValueError("invalid paired job identity")
    name = "rpi4_public_windows_build" if mode == "public" else "rpi4_windows_worker"
    request = urllib.request.Request(JOBS.format(pipeline), headers={"JOB-TOKEN": token})
    client = opener or urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    try:
        with client.open(request, timeout=10) as response:
            data = response.read(131073)
        if len(data) > 131072:
            raise ValueError
        jobs = json.loads(data)
        if not isinstance(jobs, list):
            raise ValueError
        if not jobs:
            return {"status": "created", "started_at": None}
        if len(jobs) != 1 or jobs[0]["name"] != name or jobs[0]["commit"]["id"] != source_sha:
            raise ValueError
        status = jobs[0]["status"]
        if status not in ("created", "pending", "waiting_for_resource", "preparing", "running",
                          "success", "failed", "canceled", "skipped"):
            raise ValueError
        if status in ("preparing", "running") and jobs[0].get("runner", {}).get("id") != 29:
            raise ValueError
        started = jobs[0].get("started_at")
        if status == "running":
            parsed = datetime.fromisoformat(started.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                raise ValueError
        return {"status": status, "started_at": started}
    except Exception:
        raise RuntimeError("paired Windows job status unavailable") from None
