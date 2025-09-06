from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.models import Base
from app.db import engine
from app.core.config import settings

from app.api.chat import router as chat_router
from app.api.analysis import router as analysis_router
from app.api.logs import router as logs_router

app = FastAPI(title=settings.APP_NAME)

@app.on_event("startup")
async def on_startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
