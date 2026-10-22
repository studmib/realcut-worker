"""vast.ai serverless PyWorker for 리얼컷.

provision.sh (run once by vast's base image) installs the private 리얼컷 code, ComfyUI and the models; this worker
then starts 리얼컷's job server (deploy/serverless/job_server.py, 127.0.0.1:18000) and forwards the endpoint's
signed requests to it. /make answers as NDJSON lines (stages, then each finished photo), passed straight through.

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
W = os.environ.get("WORKSPACE", "/workspace")
R = os.path.join(W, "realcut")


@asynccontextmanager
async def job_server():
    """Start the job server and wait until both ComfyUI are up (it answers /health); stopped with the worker."""
    env = dict(os.environ,
               REALCUT_COMFY_QWEN=os.path.join(W, "comfy_qwen"), REALCUT_COMFY_KREA2=os.path.join(W, "comfy_krea2"),
               REALCUT_MODELS=os.path.join(W, "models"), REALCUT_JOBS=os.path.join(W, "jobs"),
               REALCUT_ROLE="worker")  # the job server wipes each job's traces only on a worker
    env.pop("REALCUT_GIT_TOKEN", None)  # the job server never needs it
    log = open(os.path.join(W, "job_server.log"), "a")
    proc = subprocess.Popen([os.path.join(R, ".venv", "bin", "python"), "-u",
                             os.path.join(R, "deploy", "serverless", "job_server.py"), str(PORT)],
                            cwd=R, env=env, stdout=log, stderr=subprocess.STDOUT)
    for _ in range(900):  # ComfyUI's first start on a new worker takes a few minutes
        if proc.poll() is not None:
            raise RuntimeError(f"job server stopped ({proc.returncode}), see {W}/job_server.log")
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{PORT}/health", timeout=2)
            break
        except OSError:
            await asyncio.sleep(1)
    else:
        raise RuntimeError("job server not ready after 15 minutes")
    try:
        yield
    finally:
        proc.terminate()


if __name__ == "__main__":
    Worker(WorkerConfig(
        model_server_url="http://127.0.0.1",
        model_server_port=PORT,
        handlers=[
            # one batch at a time (one GPU); a batch may wait up to 15 minutes behind the one running
            HandlerConfig(route="/make", allow_parallel_requests=False, max_queue_time=900.0,
                          workload_calculator=lambda payload: 100.0),
            # the start-up benchmark runs here, not on /make (a real batch takes minutes). The job server answers
            # /bench in 2 s; with workload 1 that rates a worker at ~0.5/s, so a batch (workload 100) counts as
            # ~200 s of work, about what it takes. An instant benchmark rated it at ~50000/s and the autoscaler
            # stopped a second worker as surplus while it was running a batch.
            HandlerConfig(route="/bench", allow_parallel_requests=False, workload_calculator=lambda payload: 1.0,
                          benchmark_config=BenchmarkConfig(generator=lambda: {}, runs=1, concurrency=1,
                                                           do_warmup=False)),
        ],
        lifecycle=job_server(),
    )).run()
