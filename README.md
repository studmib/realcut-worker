# realcut-worker

vast.ai serverless worker (PyWorker) for an internal image tool.

- `provision.sh`: run once on a new worker by vast's base image: fetches the private tool code with a read-only
  token from the vast account's environment variables and installs its runtime and public models.
- `worker.py`: starts the tool's job server (127.0.0.1 only) and forwards the endpoint's signed requests to it.

No models, tool code, images or secrets live in this repository.
