from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from uuid import uuid4

import requests  # type: ignore

from core.config import settings
from core.logger import Logger
from core.message_queue import MessageQueue
from schemas.proto.face_update_pb2 import PersonUpdate  # type: ignore

logger = Logger().get_logger()


def pull_bundle(
    max_retries: int = 5,
    fallback_threshold: float = 0.5,
) -> float:

    mq = MessageQueue()

    # Get yesterday date
    now = datetime.now(ZoneInfo("Asia/Bangkok"))
    yesterday = now - timedelta(days=1)
    date = yesterday.strftime("%Y-%m-%d")

    # Pull bundle from sync server
    offset = 0
    threshold = fallback_threshold
    while True:
        retries = 0
        while retries < max_retries:
            try:
                resp = requests.get(
                    f"{settings.sync.URL}",
                    params={
                        "device_id": settings.sync.DEVICE_ID,
                        "offset": offset,
                        "limit": settings.sync.PAGE_SIZE,
                        "since": date,
                    },
                )
                bundle = resp.json()
                break
            except Exception as e:
                retries += 1
                logger.error(
                    "sync_pull_error",
                    extra={"error": e, "retry": retries},
                )
        else:
            logger.error("sync_pull_max_retries_exceeded")
            break

        threshold = bundle["threshold"]
        if bundle["users_synced"] > 0:
            for user, embeddings in dict(bundle["gallery"]).items():
                for embedding in embeddings:
                    # Send face-update event to RabbitMQ
                    msg = PersonUpdate(
                        face_id=str(uuid4()),
                        username=user,
                        embedding=embedding,
                    )
                    mq.publish(
                        body=msg.SerializeToString(),
                        routing_key=settings.rabbitmq.FACE_UPDATE_ROUTING_KEY,
                    )

        if not bundle["has_more"]:
            break

        offset += settings.sync.PAGE_SIZE

    # This is the threshold from sync server (latest)
    return threshold
