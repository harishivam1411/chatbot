from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings, validate_settings
from contextlib import asynccontextmanager
from app.db.database import engine, Base

from app.api.chat import router as chat_router
from app.api.analysis import router as analysis_router
from app.api.logs import router as logs_router

@asynccontextmanager
async def lifespan(app: FastAPI):

    validate_settings()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield  

    await engine.dispose()

app = FastAPI(
    title=settings.APP_NAME, 
    version=settings.APP_VERSION,
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router)
app.include_router(analysis_router)
app.include_router(logs_router)


@app.get("/")
async def root():
    return {"message": "Welcome to FastAPI Chatbot", "docs": "/docs"}
