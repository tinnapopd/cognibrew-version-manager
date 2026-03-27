# Cognibrew Version Manager

A scheduled Python service that daily pulls sync bundles from the cloud, publishes face-update events to RabbitMQ, and applies threshold changes to running recognition-service containers via the Docker API.

## Features

- **Edge-Pull Sync** – Scheduled daily task that pulls threshold + gallery bundles from `cognibrew-cloud-edge-sync` with pagination and retry support.
- **Face-Update Events** – Publishes Protobuf-serialised `PersonUpdate` messages to RabbitMQ for each synced user embedding.
- **Rolling Threshold Updates** – Applies similarity threshold changes to running containers with zero-downtime rolling replacement and health-check gating.
- **Docker-Aware** – Discovers target containers by label, inspects environment variables, and orchestrates start → health-check → stop → rename flows.

## Project Structure

```text
src/
├── core/
│   ├── config.py                # Pydantic settings (RabbitMQ, Docker, Sync)
│   ├── logger.py                # JSON structured logger
│   └── message_queue.py         # RabbitMQ publisher
├── processors/
│   ├── pull_processor.py        # Pull bundle from sync server & publish to MQ
│   └── upgrade_processor.py     # Rolling-update container threshold via Docker
├── schemas/
│   └── proto/                   # Compiled protobuf (face_update_pb2.py)
└── main.py                      # Scheduled entry-point (daily sync task)
```

## Getting Started

### Prerequisites

- Python 3.10+
- Docker Engine (for container management)
- RabbitMQ (for face-update events)
- `cognibrew-cloud-edge-sync` service running (for sync pulls)

### Local Development

```bash
# 1. Clone and install dependencies
pip install -r requirements.txt

# 2. Copy and edit environment variables
cp .env.example .env

# 3. Run the service
python src/main.py
```

### Docker

```bash
docker build -t cognibrew-version-manager .
docker run --env-file .env cognibrew-version-manager
```

## Configuration

All settings are loaded from environment variables (see `.env.example`):

| Variable | Description | Default |
| --- | --- | --- |
| `LOG_LEVEL` | Logging level | `INFO` |
| `RABBITMQ_HOST` | RabbitMQ hostname | `localhost` |
| `RABBITMQ_PORT` | RabbitMQ port | `5672` |
| `RABBITMQ_USERNAME` | RabbitMQ user | `guest` |
| `RABBITMQ_PASSWORD` | RabbitMQ password | `guest` |
| `RABBITMQ_FACE_UPDATE_EXCHANGE_NAME` | Exchange for face-update events | `cognibrew.vectordb` |
| `RABBITMQ_FACE_UPDATE_QUEUE_NAME` | Queue for face-update events | `cognibrew.vectordb.face_updated` |
| `RABBITMQ_FACE_UPDATE_ROUTING_KEY` | Routing key for face-update events | `face.updated` |
| `DOCKER_TARGET_LABEL` | Label used to discover containers | `cognibrew.service=recognition` |
| `DOCKER_HEALTH_TIMEOUT_S` | Health-check timeout (seconds) | `30` |
| `DOCKER_HEALTH_POLL_S` | Health-check poll interval (seconds) | `1` |
| `SYNC_URL` | Cloud-edge-sync bundle endpoint | `http://edge-sync.melierx.com/api/v1/sync/bundle` |
| `SYNC_DEVICE_ID` | Device identifier (defaults to MAC address) | Auto-detected |
| `SYNC_PAGE_SIZE` | Max users per sync page | `50` |
| `SYNC_SCHEDULE_TIME` | Daily sync time (HH:MM) | `01:00` |
| `SYNC_CHECK_EVERY` | Schedule poll interval (seconds) | `60` |

## CI / CD

The GitHub Actions workflow (`.github/workflows/ci.yml`) runs on push/PR to `main`:

1. **Lint** – Ruff static analysis
2. **Build & Push** – Docker image pushed to Docker Hub on version tags (`v*`)
