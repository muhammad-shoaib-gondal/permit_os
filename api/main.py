from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from api.routes.audit import router as audit_router
from api.routes.cases import router as cases_router
from api.services.case_service import init_db

DISCLAIMER = (
    "PermitOS provides pre-screening assistance only. It does not constitute legal, "
    "engineering, or architectural advice. All filings require review by licensed "
    "professionals and approval by applicable authorities."
)

WEB_DIST = Path(__file__).resolve().parents[1] / "web" / "dist"

# Load .env so LLM_BACKEND / HF_TOKEN are available to the agent pipeline
load_dotenv(Path(__file__).resolve().parents[1] / ".env")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title="PermitOS API",
    description="Multi-agent permitting command center — Band of Agents Hackathon",
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

app.include_router(cases_router)
app.include_router(audit_router)


@app.get("/health")
async def health():
    return {"status": "ok", "product": "PermitOS"}


@app.get("/disclaimer")
async def disclaimer():
    return {"disclaimer": DISCLAIMER}


if WEB_DIST.exists():
    app.mount("/assets", StaticFiles(directory=WEB_DIST / "assets"), name="assets")

    @app.get("/")
    async def serve_ui():
        return FileResponse(WEB_DIST / "index.html")
