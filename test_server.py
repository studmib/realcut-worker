"""Stand-in model server for the test worker (worker.py). Listens on 127.0.0.1 only.

POST /make  {"seconds": N}  waits N seconds, then reports this start and the disk marker
POST /bench {}              answers at once (start-up benchmark)
GET  /health                200 when up
"""
import json
import os
import socket
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

STARTED = time.time()
MARKER = os.path.join(os.environ.get("WORKSPACE_DIR", "/workspace"), "realcut_test_marker")
if not os.path.exists(MARKER):  # the first start of this worker's disk
    with open(MARKER, "w") as f:
        f.write(str(STARTED))
with open(MARKER) as f:
    FIRST_START = float(f.read().strip() or STARTED)


class Handler(BaseHTTPRequestHandler):
    def _json(self, obj: dict) -> None:
        body = json.dumps(obj).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        self._json({"ok": True})

    def do_POST(self) -> None:
        payload = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
        seconds = min(float(payload.get("seconds") or 0), 900.0)
        time.sleep(seconds)
        self._json({
            "route": self.path,
            "slept": seconds,
            "host": socket.gethostname(),
            "this_start": STARTED,
            "first_start_of_disk": FIRST_START,
            "disk_kept_from_earlier_start": FIRST_START < STARTED - 1,
            "now": time.time(),
        })

    def log_message(self, fmt, *args) -> None:
        pass


ThreadingHTTPServer(("127.0.0.1", int(sys.argv[1])), Handler).serve_forever()
