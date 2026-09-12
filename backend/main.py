from __future__ import annotations

from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.database.database import Base, engine
from backend.api.routes import router

Path("data").mkdir(exist_ok=True)
Base.metadata.create_all(bind=engine)

app = FastAPI(title="WISE MOM Backend", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)
