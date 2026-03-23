import asyncio
import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

import uvicorn
from fastapi import FastAPI

from api.face_update import router as face_update_router
from api.recognition_config import router as config_router
from api.sync import router as sync_router
import core.sync_client as sync_client_mod


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Start the background sync loop on startup."""
    task = asyncio.create_task(sync_client_mod.start_sync_loop())
    yield
    task.cancel()


app = FastAPI(
    title="Cognibrew Version Manager",
    description=(
        "Manage running service configuration, push face-update "
        "events to RabbitMQ, and pull sync bundles from cloud."
    ),
    version="0.2.0",
    lifespan=lifespan,
)

app.include_router(config_router)
app.include_router(face_update_router)
app.include_router(sync_router)

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        log_level=os.getenv("LOG_LEVEL", "info").lower(),
    )
