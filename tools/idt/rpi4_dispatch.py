"""Start the paired Windows job using this project's GitLab job token."""
from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request

ENDPOINT = "https://gitlab.saffti.jp/api/v4/projects/38/trigger/pipeline"


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
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *_args, **_kwargs):
            return None
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
