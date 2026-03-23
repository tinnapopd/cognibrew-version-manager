# Cognibrew Version Manager

A FastAPI service that manages running recognition-service containers, publishes face-update events to RabbitMQ, and pulls daily sync bundles from the cloud.

## Features

- **Rolling Config Updates** – Update `MODEL_SIMILARITY_THRESHOLD` on running containers via the Docker API with zero-downtime rolling replacement and health-check gating.
- **Face-Update Events** – Publish Protobuf-serialised `PersonUpdate` messages (CREATE / UPDATE / DELETE) to RabbitMQ.
- **Edge-Pull Sync** – Background loop that daily pulls threshold + gallery bundles from `cognibrew-cloud-edge-sync` and applies them (rolling-update containers + publish gallery to RabbitMQ).
- **Docker-Aware** – Discovers target containers by label, inspects environment variables, and orchestrates start → health-check → stop → rename flows.

## Project Structure

```text
src/
├── api/
│   ├── face_update.py           # POST /face-update
│   ├── recognition_config.py    # GET/PUT /config/threshold
│   └── sync.py                  # GET /sync/status, POST /sync/trigger
├── core/
│   ├── config.py                # Pydantic settings (RabbitMQ, Docker, Sync)
│   ├── logger.py                # JSON structured logger
│   ├── message_queue.py         # RabbitMQ publisher
│   └── sync_client.py           # Edge-pull sync client (pull + apply)
├── schemas/
│   ├── face_update.py           # Face-update Pydantic models
│   ├── recognition_config.py    # Threshold Pydantic models
│   ├── sync.py                  # Sync bundle & status models
│   └── proto/                   # Compiled protobuf
└── main.py                      # FastAPI entry-point with sync lifespan
tests/
├── conftest.py                  # Shared fixtures (TestClient, mock Docker)
├── test_api_face_update.py
├── test_api_recognition_config.py
├── test_api_sync.py
└── test_sync_client.py
```

## API Endpoints

| Method | Path                          | Description                                |
| ------ | ----------------------------- | ------------------------------------------ |
| GET    | `/config/threshold`           | Read threshold from all target containers  |
| PUT    | `/config/threshold`           | Rolling-update threshold on all targets    |
| POST   | `/face-update/face-update`    | Publish a face-update event to RabbitMQ    |
| GET    | `/sync/status`                | Current edge-pull sync state               |
| POST   | `/sync/trigger`               | Manually trigger an immediate sync pull    |

## Getting Started

### Prerequisites

- Python 3.10+
- Docker Engine (for container management endpoints)
- RabbitMQ (for face-update events)
- `cognibrew-cloud-edge-sync` service running (for sync pulls)

### Local Development

```bash
# 1. Clone and install dependencies
pip install -r requirements.txt

# 2. Copy and edit environment variables
cp .env.example .env

# 3. Run the dev server
uvicorn src.main:app --reload --port 8000
```

### Docker

```bash
docker build -t cognibrew-version-manager .
docker run -p 8000:8000 --env-file .env cognibrew-version-manager
```

## Configuration

All settings are loaded from environment variables (see `.env.example`):

| Variable                             | Description                          | Default                |
| ------------------------------------ | ------------------------------------ | ---------------------- |
| `LOG_LEVEL`                          | Logging level                        | `INFO`                 |
| `RABBITMQ_HOST`                      | RabbitMQ hostname                    | `localhost`            |
| `RABBITMQ_PORT`                      | RabbitMQ port                        | `5672`                 |
| `RABBITMQ_USERNAME`                  | RabbitMQ user                        | `guest`                |
| `RABBITMQ_PASSWORD`                  | RabbitMQ password                    | `guest`                |
| `RABBITMQ_FACE_UPDATE_EXCHANGE_NAME` | Exchange for face-update events      | —                      |
| `RABBITMQ_FACE_UPDATE_QUEUE_NAME`    | Queue for face-update events         | —                      |
| `RABBITMQ_FACE_UPDATE_ROUTING_KEY`   | Routing key for face-update events   | —                      |
| `DOCKER_TARGET_LABEL`                | Label used to discover containers    | —                      |
| `DOCKER_HEALTH_TIMEOUT_S`           | Health-check timeout (seconds)       | `30`                   |
| `DOCKER_HEALTH_POLL_S`              | Health-check poll interval (seconds) | `1`                    |
| `SYNC_CLOUD_URL`                     | Cloud-edge-sync service base URL     | `http://localhost:8004`|
| `SYNC_INTERVAL_HOURS`               | Pull interval in hours               | `24`                   |
| `SYNC_PAGE_SIZE`                     | Max users per sync page              | `50`                   |
| `SYNC_ENABLED`                       | Enable/disable background sync loop  | `true`                 |

## Testing

```bash
pytest tests/ -v
```

## CI / CD

The GitHub Actions workflow (`.github/workflows/ci.yml`) runs on every push/PR to `main`:

1. **Lint** – Ruff static analysis
2. **Test** – Pytest suite
3. **Build & Push** – Docker image pushed to Docker Hub on version tags (`v*`)
