import os

import uvicorn
from fastapi import FastAPI

from api.recognition_config import router as config_router
from api.face_update import router as face_update_router

app = FastAPI(
    title="Cognibrew Version Manager",
    description=(
        "Manage running service configuration and push face-update "
        "events to RabbitMQ."
    ),
    version="0.1.0",
)

app.include_router(config_router)
app.include_router(face_update_router)

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        log_level=os.getenv("LOG_LEVEL", "info").lower(),
    )
