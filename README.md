# Cognibrew Version Manager

A FastAPI service that manages running recognition-service containers and publishes face-update events to RabbitMQ.

## Features

- **Rolling Config Updates** – Update `MODEL_SIMILARITY_THRESHOLD` on running containers via the Docker API with zero-downtime rolling replacement and health-check gating.
- **Face-Update Events** – Publish Protobuf-serialised `PersonUpdate` messages (CREATE / UPDATE / DELETE) to RabbitMQ.
- **Docker-Aware** – Discovers target containers by label, inspects environment variables, and orchestrates start → health-check → stop → rename flows.

## Project Structure

```text
src/
├── api/
│   ├── face_update.py           # POST /face-update
│   └── recognition_config.py    # GET/PUT /config/threshold
├── core/
│   ├── config.py                # Pydantic settings
│   ├── logger.py                # JSON structured logger
│   └── message_queue.py         # RabbitMQ publisher
├── schemas/                     # Pydantic models & compiled protobuf
└── main.py                      # FastAPI application entry-point
tests/
├── conftest.py                  # Shared fixtures (TestClient, mock Docker)
├── test_api_face_update.py
└── test_api_recognition_config.py
```

## API Endpoints

| Method | Path                          | Description                              |
| ------ | ----------------------------- | ---------------------------------------- |
| GET    | `/config/threshold`           | Read threshold from all target containers |
| PUT    | `/config/threshold`           | Rolling-update threshold on all targets   |
| POST   | `/face-update/face-update`    | Publish a face-update event to RabbitMQ   |

## Getting Started

### Prerequisites

- Python 3.10+
- Docker Engine (for container management endpoints)
- RabbitMQ (for face-update events)

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

| Variable                             | Description                          | Default     |
| ------------------------------------ | ------------------------------------ | ----------- |
| `LOG_LEVEL`                          | Logging level                        | `INFO`      |
| `RABBITMQ_HOST`                      | RabbitMQ hostname                    | `localhost` |
| `RABBITMQ_PORT`                      | RabbitMQ port                        | `5672`      |
| `RABBITMQ_USERNAME`                  | RabbitMQ user                        | `guest`     |
| `RABBITMQ_PASSWORD`                  | RabbitMQ password                    | `guest`     |
| `RABBITMQ_FACE_UPDATE_EXCHANGE_NAME` | Exchange for face-update events      | —           |
| `RABBITMQ_FACE_UPDATE_QUEUE_NAME`    | Queue for face-update events         | —           |
| `RABBITMQ_FACE_UPDATE_ROUTING_KEY`   | Routing key for face-update events   | —           |
| `DOCKER_TARGET_LABEL`                | Label used to discover containers    | —           |
| `DOCKER_HEALTH_TIMEOUT_S`           | Health-check timeout (seconds)       | `30`        |
| `DOCKER_HEALTH_POLL_S`              | Health-check poll interval (seconds) | `1`         |

## Testing

```bash
pytest tests/ -v
```

## CI / CD

The GitHub Actions workflow (`.github/workflows/ci.yml`) runs on every push/PR to `main`:

1. **Lint** – Ruff static analysis
2. **Test** – Pytest suite
3. **Build & Push** – Docker image pushed to Docker Hub on version tags (`v*`)
