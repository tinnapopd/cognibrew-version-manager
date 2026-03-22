from fastapi import APIRouter, HTTPException

from schemas import FaceUpdateRequest, MessageResponse
from core.config import settings
from core.logger import Logger
from core.message_queue import MessageQueue
from schemas.proto.face_update_pb2 import PersonUpdate  # type: ignore

logger = Logger().get_logger()

router = APIRouter(prefix="/face-update", tags=["face-update"])

# Lazy initialization
_mq: MessageQueue | None = None

_ACTION_MAP: dict[str, int] = {
    "CREATE": PersonUpdate.CREATE,
    "UPDATE": PersonUpdate.UPDATE,
    "DELETE": PersonUpdate.DELETE,
}


def _get_mq() -> MessageQueue:
    global _mq
    if _mq is None:
        _mq = MessageQueue(
            exchange_name=settings.rabbitmq.FACE_UPDATE_EXCHANGE_NAME,
            queue_name=settings.rabbitmq.FACE_UPDATE_QUEUE_NAME,
        )
        _mq.connect()
    return _mq


@router.post("/face-update", response_model=MessageResponse)
def publish_face_update(body: FaceUpdateRequest) -> MessageResponse:
    try:
        msg = PersonUpdate(
            person_id=body.person_id,
            username=body.username,
            embedding=body.embedding,
            action=_ACTION_MAP[body.action],
        )

        mq = _get_mq()
        mq.publish(
            body=msg.SerializeToString(),
            routing_key=settings.rabbitmq.FACE_UPDATE_ROUTING_KEY,
        )

        logger.info(
            "face_update_published",
            extra={
                "person_id": body.person_id,
                "action": body.action,
            },
        )

        return MessageResponse(
            status="ok",
            detail=(f"{body.action} published for person '{body.person_id}'"),
        )

    except Exception as exc:
        logger.exception("face_update_publish_failed")
        detail = str(exc) or f"{type(exc).__name__}: connection failed"
        raise HTTPException(status_code=500, detail=detail)
