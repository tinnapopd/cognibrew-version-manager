#!/usr/bin/env bash

set -x
set -eo pipefail

if ! [ -x "$(command -v docker)" ]; then
    echo >&2 "Error: Docker is not installed."
    exit 1
fi

# RabbitMQ configuration
RABBITMQ_PORT=${RABBITMQ_PORT:-5672}
RABBITMQ_MANAGEMENT_PORT=${RABBITMQ_MANAGEMENT_PORT:-15672}
RABBITMQ_DEFAULT_USER=${RABBITMQ_DEFAULT_USER:-guest}
RABBITMQ_DEFAULT_PASS=${RABBITMQ_DEFAULT_PASS:-guest}

# Recognition (inference server --> recognition service)
RABBITMQ_INFERENCE_EXCHANGE=${RABBITMQ_INFERENCE_EXCHANGE:-cognibrew.inference}
RABBITMQ_FACE_EMBEDDED_ROUTING_KEY=${RABBITMQ_FACE_EMBEDDED_ROUTING_KEY:-face.embedded}

# Face update (cloud --> vectordb)
RABBITMQ_FACE_UPDATE_EXCHANGE=${RABBITMQ_FACE_UPDATE_EXCHANGE:-cognibrew.vectordb}
RABBITMQ_FACE_UPDATE_ROUTING_KEY=${RABBITMQ_FACE_UPDATE_ROUTING_KEY:-face.updated}


# Launch RabbitMQ using Docker
# Allow to skip docker if a dockerized RabbitMQ is already running
# Use: SKIP_DOCKER=1 ./scripts/init_rabbitmq.sh
if [[ -z "${SKIP_DOCKER}" ]]; then
    # Remove any previous RabbitMQ docker container
    docker rm -f rabbitmq || true
    docker run \
        --name rabbitmq \
        -p "${RABBITMQ_PORT}":5672 \
        -p "${RABBITMQ_MANAGEMENT_PORT}":15672 \
        -e RABBITMQ_DEFAULT_USER="${RABBITMQ_DEFAULT_USER}" \
        -e RABBITMQ_DEFAULT_PASS="${RABBITMQ_DEFAULT_PASS}" \
        -d rabbitmq:3-management
fi

# Keep pinging RabbitMQ until it's ready
until curl -sf "http://localhost:${RABBITMQ_MANAGEMENT_PORT}/api/healthchecks/node" -u "${RABBITMQ_DEFAULT_USER}:${RABBITMQ_DEFAULT_PASS}" > /dev/null 2>&1; do
    >&2 echo "RabbitMQ is still unavailable - sleeping"
    sleep 5
done

>&2 echo "RabbitMQ is up and running on port ${RABBITMQ_PORT} (AMQP), ${RABBITMQ_MANAGEMENT_PORT} (Management), ready to go!"
