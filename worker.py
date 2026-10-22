"""vast.ai serverless PyWorker for 리얼컷 — TEST VERSION.

The model server here (test_server.py) only waits and reports, to measure on vast.ai:
  - whether a request of several minutes goes through (the real pipeline takes 3-5 minutes per batch)
  - whether a stopped (inactive) worker keeps its disk (a marker file written on the first start)
  - how long a cold start takes

This repository is public: it holds no models, no 리얼컷 code and no secrets.
"""
import asyncio
import os
import subprocess
import sys
import urllib.request
from contextlib import asynccontextmanager

from vastai import BenchmarkConfig, HandlerConfig, Worker, WorkerConfig

PORT = 18000
HERE = os.path.dirname(os.path.abspath(__file__))


@asynccontextmanager
async def model_server():
    """Start the model server and wait until it answers; stopped again when the worker stops."""
    proc = subprocess.Popen([sys.executable, os.path.join(HERE, "test_server.py"), str(PORT)])
    for _ in range(300):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{PORT}/health", timeout=2)
            break
        except OSError:
            await asyncio.sleep(1)
    try:
        yield
    finally:
        proc.terminate()


if __name__ == "__main__":
    Worker(WorkerConfig(
        model_server_url="http://127.0.0.1",
        model_server_port=PORT,
        handlers=[
            # one batch at a time (one GPU); a request may wait up to 15 minutes behind the one running
            HandlerConfig(route="/make", allow_parallel_requests=False, max_queue_time=900.0,
                          workload_calculator=lambda payload: 100.0),
            # the start-up benchmark runs here, not on /make (a real batch would take minutes)
            HandlerConfig(route="/bench", allow_parallel_requests=False,
                          benchmark_config=BenchmarkConfig(generator=lambda: {"seconds": 0}, runs=1,
                                                           concurrency=1, do_warmup=False)),
        ],
        lifecycle=model_server(),
    )).run()
