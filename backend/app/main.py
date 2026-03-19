from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os

from app.core.config import settings
from app.core.database import engine
from app.models import user, project, api_doc, api_endpoint, test_case, test_result

app = FastAPI(title="AIATP", version="1.0.0")

cors_origins = os.getenv("CORS_ORIGINS", "*")
allow_origins = cors_origins.split(",") if cors_origins != "*" else ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}
