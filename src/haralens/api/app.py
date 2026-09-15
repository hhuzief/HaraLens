"""FastAPI composition root."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from haralens import __version__
from haralens.api.health import router
from haralens.common.config import Settings
from haralens.common.logging import configure_logging


def create_app(settings: Settings | None = None) -> FastAPI:
    configuration = settings if settings is not None else Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        configure_logging(configuration.log_level)
        logger = logging.getLogger("haralens.api")
        logger.info("api_started")
        yield
        logger.info("api_stopped")

    app = FastAPI(title="HaraLens API", version=__version__, lifespan=lifespan)
    app.include_router(router)
    return app
