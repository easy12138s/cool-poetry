import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import engine, get_db
from .routers import chat
from .services.config import ConfigManager

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    from .database import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        await ConfigManager.initialize(db)
        logger.info("ConfigManager initialized")

    yield

    await ConfigManager.shutdown()
    await engine.dispose()
    logger.info("Application shutdown")


app = FastAPI(
    title="小诗仙 API",
    description="儿童AI古诗陪伴应用后端服务",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router, prefix="/api/v1")


@app.get("/")
async def root():
    return {"message": "小诗仙 API", "version": "0.1.0"}
