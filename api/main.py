from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from api.routes.audit import router as audit_router
from api.routes.cases import router as cases_router
from api.routes.jurisdictions import router as jurisdictions_router
from api.routes.projects import router as projects_router
from api.services.case_service import init_db

DISCLAIMER = (
    "EstatePermit provides pre-screening assistance only. It does not constitute legal, "
    "engineering, or architectural advice. All filings require review by licensed "
    "professionals and approval by applicable authorities."
)

ROOT = Path(__file__).resolve().parents[1]
WEB_DIST = ROOT / "web" / "dist"
LANDING_INDEX = WEB_DIST / "index.html"
APP_DIST = WEB_DIST / "app"
APP_INDEX = APP_DIST / "index.html"

load_dotenv(ROOT / ".env")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title="EstatePermit API",
    description="AI permitting command center",
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


@app.middleware("http")
async def redirect_spa_browser_routes(request: Request, call_next):
    path = request.url.path
    accepts_html = "text/html" in request.headers.get("accept", "")
    if accepts_html and (path.startswith("/projects/") or path == "/settings"):
        target = f"/app{path}"
        if request.url.query:
            target += f"?{request.url.query}"
        return RedirectResponse(target, status_code=302)
    return await call_next(request)

app.include_router(cases_router)
app.include_router(audit_router)
app.include_router(projects_router)
app.include_router(jurisdictions_router)


@app.get("/health")
async def health():
    return {"status": "ok", "product": "EstatePermit"}


@app.get("/disclaimer")
async def disclaimer():
    return {"disclaimer": DISCLAIMER}


if WEB_DIST.exists():
    for sub in ("css", "js"):
        static_dir = WEB_DIST / sub
        if static_dir.is_dir():
            app.mount(f"/{sub}", StaticFiles(directory=static_dir), name=f"landing-{sub}")

    app_assets = WEB_DIST / "assets"
    if app_assets.is_dir():
        app.mount("/assets", StaticFiles(directory=app_assets), name="app-assets")

    sample_brief = WEB_DIST / "sample-project-brief.json"
    if sample_brief.is_file():

        @app.get("/sample-project-brief.json")
        async def sample_project_brief():
            return FileResponse(sample_brief)

    @app.get("/")
    async def serve_landing():
        if LANDING_INDEX.is_file():
            return FileResponse(LANDING_INDEX)
        if APP_INDEX.is_file():
            return FileResponse(APP_INDEX)
        return {"error": "UI not built - run npm run build in web/"}

    @app.get("/app")
    @app.get("/app/")
    @app.get("/app/{full_path:path}")
    async def serve_app(full_path: str = ""):
        if APP_INDEX.is_file():
            return FileResponse(APP_INDEX)
        return {"error": "App not built - run npm run build in web/"}
