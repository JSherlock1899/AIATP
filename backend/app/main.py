from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os

from app.core.config import settings
from app.core.database import engine
from app.models import user, project, api_doc, api_endpoint, test_case, test_result
from app.api.auth import router as auth_router
from app.api.projects import router as projects_router
from app.api.api_docs import router as api_docs_router

app = FastAPI(title="AIATP", version="1.0.0")

app.include_router(auth_router)
app.include_router(projects_router)
app.include_router(api_docs_router)

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
