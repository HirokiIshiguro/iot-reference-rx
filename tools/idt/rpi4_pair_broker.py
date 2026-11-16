"""Launch one paired Windows job only when a local build request arrives."""
from __future__ import annotations

import secrets
import queue
import os
import select
from datetime import datetime, timezone
import socket
import threading
import time

from tools.idt import rpi4_pair as pair, rpi4_pair_agent as agent
from tools.idt.rpi4_dispatch import trigger_worker, worker_status

READY_SECONDS = pair.READY_SECONDS
POLL_SECONDS = 5


class Broker:
    def __init__(self, token, ref, pipeline, source_sha, mode, *, build_seconds, queue_seconds):
        self.token, self.ref, self.pipeline = token, ref, pipeline
        self.source_sha, self.mode, self.build_seconds = source_sha, mode, build_seconds
        if type(queue_seconds) is not int or queue_seconds <= 0:
            raise ValueError("no reviewed time remains for a paired worker")
        self.queue_deadline = time.monotonic() + queue_seconds
        self.queue_seconds = queue_seconds
        self.stop = threading.Event()
        self.error = None
        self.server = self.thread = None

    def start(self):
        agent.prepare(self.pipeline)
        self.endpoint = agent.session_path(self.pipeline) / "build.sock"
        self.server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.server.bind(str(self.endpoint))
        self.endpoint.chmod(0o600)
        self.server.listen(1)
        self.server.settimeout(0.25)
        self.thread = threading.Thread(target=self.serve, name="paired-build-broker", daemon=True)
        self.thread.start()

    def build(self, request):
        remaining = int(self.queue_deadline - time.monotonic())
        if remaining <= 0:
            raise RuntimeError("no paired-worker queue time remains")
        # The per-request session name is not a GitLab pipeline ID.
        session = str(secrets.randbelow(9 * 10**18) + 10**18)
        agent.prepare(session)
        downstream = trigger_worker(self.token, self.ref, self.pipeline, self.source_sha, session, self.mode,
                                    self.build_seconds)
        print("Paired Windows pipeline started: " + str(downstream), flush=True)
        remaining = int(self.queue_deadline - time.monotonic())
        if remaining <= 0:
            raise RuntimeError("no paired-worker queue time remains")
        self.wait_ready(session, downstream, remaining)
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
            connection.settimeout(self.build_seconds)
            connection.connect(str(agent.session_path(session) / "build.sock"))
            with connection.makefile("rwb", buffering=0) as stream:
                pair.write_frame(stream, request)
                response = pair.read_frame(stream)
        agent.shutdown(session, 30)
        endpoint = agent.session_path(session) / "build.sock"
        deadline = time.monotonic() + 30
        while endpoint.exists() and time.monotonic() < deadline:
            time.sleep(0.1)
        agent.cleanup(session)
        return response

    def wait_ready(self, session, pipeline, queue_seconds):
        """Count connection time only after job start, within the queue budget."""
        events = queue.Queue()
        stop = threading.Event()
        reader, keepalive = agent.open_ready(session)
        def watch_job():
            while not stop.is_set():
                try:
                    status = worker_status(self.token, pipeline, self.source_sha, self.mode)
                    events.put(("status", status))
                except BaseException as error:
                    events.put(("error", error))
                    return
                if stop.wait(POLL_SECONDS):
                    return
        threading.Thread(target=watch_job, name="paired-job-status", daemon=True).start()
        deadline = time.monotonic() + queue_seconds
        started = False
        try:
            while True:
                if select.select([reader], [], [], 0)[0]:
                    if os.read(reader, 1) != b"R":
                        raise RuntimeError("paired worker readiness failed")
                    return
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise RuntimeError("paired worker exceeded its reviewed wait budget")
                try:
                    kind, value = events.get_nowait()
                except queue.Empty:
                    select.select([reader], [], [], min(remaining, 0.2))
                    continue
                if kind == "error":
                    if select.select([reader], [], [], 0)[0] and os.read(reader, 1) == b"R":
                        return
                    raise RuntimeError("paired worker readiness failed") from None
                status = value["status"]
                if status == "running" and not started:
                    started = True
                    actual_start = datetime.fromisoformat(value["started_at"].replace("Z", "+00:00"))
                    elapsed = max(0, (datetime.now(timezone.utc) - actual_start).total_seconds())
                    deadline = time.monotonic() + max(0, READY_SECONDS - elapsed)
                elif status in ("failed", "canceled", "skipped", "success"):
                    if select.select([reader], [], [], 0)[0] and os.read(reader, 1) == b"R":
                        return
                    raise RuntimeError("paired worker ended before readiness")
        finally:
            stop.set()
            os.close(keepalive)
            os.close(reader)

    def serve(self):
        try:
            while not self.stop.is_set():
                try:
                    connection, _ = self.server.accept()
                except socket.timeout:
                    continue
                with connection, connection.makefile("rwb", buffering=0) as client:
                    try:
                        request = pair.read_frame(client)
                        response = self.build(request)
                        pair.write_frame(client, response)
                    except BaseException as error:
                        self.error = error
                        try:
                            pair.write_frame(client, {"kind": "error"})
                        except Exception:
                            pass
                        return
        finally:
            self.server.close()
            self.endpoint.unlink(missing_ok=True)

    def close(self):
        self.stop.set()
        self.thread.join(timeout=30)
        if self.thread.is_alive():
            raise RuntimeError("paired build is still active; retain its sessions")
        if self.error is not None:
            raise RuntimeError("paired build failed; retain its sessions") from None
        agent.cleanup(self.pipeline)
