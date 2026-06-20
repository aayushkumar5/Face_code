# Production Deployment

FaceCode ships with a small single-host production topology:

- Nginx serves the compiled React application, applies global request limits,
  and proxies API and WebSocket traffic.
- The API container owns the ML model and SQLite database but cannot directly
  execute submissions in production mode.
- A secret-free runner container executes submissions on an internal network.
  It has a read-only filesystem, a bounded temporary directory, no outbound
  network, no Linux capabilities, and CPU, memory, and process limits.

## Start

1. Copy `.env.example` to `.env` and replace both secrets with independent
   random values of at least 32 characters.
2. Set the public HTTPS origin and hostname.
3. Run `docker compose up --build -d`.
4. Terminate TLS in a cloud load balancer or a host-level reverse proxy in
   front of port 8080.

Do not publish the backend or runner ports. Only the frontend service should
be reachable from outside the Docker network.

## Render Demo

`render.yaml` defines a three-service free-tier demo deployment. Create a new
Render Blueprint from this repository and Render will provision the frontend,
backend, runner, and shared runner secret. Free services can sleep when idle,
and the SQLite database uses ephemeral storage, so this option is for demos
only. Use the Docker Compose topology with persistent storage for production.

## Operations

- Back up the `facecode_data` Docker volume regularly and test restoration.
- Monitor `/healthz` externally and `/api/health` internally.
- Forward container logs to a centralized store and alert on HTTP 5xx rates,
  runner failures, disk usage, and sustained resource saturation.
- Rotate both secrets by replacing the deployment. Rotating the session secret
  invalidates active browser sessions.
- Apply dependency and base-image updates routinely, then rerun CI and a
  staging smoke test.

This configuration deliberately runs one API process because adaptive state is
held in memory. Horizontal scaling requires moving that state to Redis and the
database to PostgreSQL. SQLite in WAL mode is suitable for a small, single-host
deployment, not a multi-instance service.

## Privacy

Webcam frames are processed in memory and are not intentionally persisted.
Session analytics store the dominant emotion and aggregate confidence values.
Records older than `FACECODE_RETENTION_DAYS` are deleted at API startup. An
authenticated client can delete its records through `DELETE /api/session-data`.
Before accepting real users, publish a privacy notice covering purpose,
retention, deletion, model limitations, and contact details. Obtain explicit
camera consent and avoid presenting inferred emotion as a medical or factual
assessment of the user.

## Runner Boundary

The runner combines AST restrictions with container isolation. Standard Linux
containers are still weaker than microVMs. For a hostile public workload,
deploy the runner with gVisor, Kata Containers, or Firecracker and add per-job
disposable isolation rather than reusing a long-lived container.
