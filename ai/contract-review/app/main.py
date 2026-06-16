from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.api.v1.routes.contracts import router as contracts_router
from app.core.config import settings
from app.core.exceptions import AppError
from app.core.logging import bind_request_id, get_logger, setup_logging
from app.infrastructure.db.session import init_db

setup_logging(settings.log_level)
logger = get_logger(__name__)
templates = Jinja2Templates(directory="app/templates")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("app_starting", app=settings.app_name)
    await init_db()
    yield
    logger.info("app_shutdown")


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Agentic AI Contract Review System with LangGraph and Gemini",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    request_id = bind_request_id(request.headers.get("X-Request-ID"))
    logger.info("request_start", method=request.method, path=request.url.path, request_id=request_id)
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    logger.info("request_end", status=response.status_code, request_id=request_id)
    return response


@app.exception_handler(AppError)
async def app_error_handler(_request: Request, exc: AppError):
    status_code = 404 if exc.code == "not_found" else 400
    return JSONResponse(status_code=status_code, content={"error": {"code": exc.code, "message": exc.message}})


app.include_router(contracts_router, prefix="/api/v1")

try:
    app.mount("/static", StaticFiles(directory="app/static"), name="static")
except RuntimeError:
    pass


@app.get("/", response_class=HTMLResponse)
async def upload_page(request: Request):
    return templates.TemplateResponse("upload.html", {"request": request})


@app.get("/health")
async def health():
    return {"status": "ok", "llm_provider": settings.llm_provider, "model": settings.gemini_chat_model}
