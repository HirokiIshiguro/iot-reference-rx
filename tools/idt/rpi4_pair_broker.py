"""Launch one paired Windows job only when a local build request arrives."""
from __future__ import annotations

import secrets
import socket
import threading
import time

from tools.idt import rpi4_pair as pair, rpi4_pair_agent as agent
from tools.idt.rpi4_dispatch import trigger_worker


class Broker:
    def __init__(self, token, ref, pipeline, source_sha, mode, *, build_seconds=3600):
        self.token, self.ref, self.pipeline = token, ref, pipeline
        self.source_sha, self.mode, self.build_seconds = source_sha, mode, build_seconds
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
        # The per-request session name is not a GitLab pipeline ID.
        session = str(secrets.randbelow(9 * 10**18) + 10**18)
        agent.prepare(session)
        downstream = trigger_worker(self.token, self.ref, self.pipeline, self.source_sha, session, self.mode,
                                    self.build_seconds)
        print("Paired Windows pipeline started: " + str(downstream), flush=True)
        agent.wait_ready(session, 600)
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
