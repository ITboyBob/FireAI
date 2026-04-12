import hashlib
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.api.chat import router as chat_router
from app.api.conversations import router as conversations_router
from app.api.health import router as health_router


APP_DIR = Path(__file__).resolve().parent
TEMPLATES = Jinja2Templates(directory=str(APP_DIR / "templates"))
STATIC_DIR = APP_DIR / "static"


def build_static_asset_url(request: Request, asset_name: str) -> str:
    asset_path = STATIC_DIR / asset_name
    version = hashlib.sha256(asset_path.read_bytes()).hexdigest()[:12]
    return f"{request.url_for('static', path=f'/{asset_name}')}?v={version}"


def create_app() -> FastAPI:
    app = FastAPI(title="消防问答系统 2.0")
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    def render_shell(request: Request, *, initial_conversation_id: str = "") -> HTMLResponse:
        response = TEMPLATES.TemplateResponse(
            request=request,
            name="index.html",
            context={
                "page_title": "消防问答系统 2.0",
                "conversation_endpoint": "/api/conversations",
                "initial_conversation_id": initial_conversation_id,
                "static_css_url": build_static_asset_url(request, "app.css"),
                "static_js_url": build_static_asset_url(request, "app.js"),
            },
        )
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/", response_class=HTMLResponse, tags=["web"])
    async def index(request: Request) -> HTMLResponse:
        return render_shell(request)

    @app.get("/conversations/{conversation_id}", response_class=HTMLResponse, tags=["web"])
    async def conversation_page(request: Request, conversation_id: str) -> HTMLResponse:
        return render_shell(request, initial_conversation_id=conversation_id)

    app.include_router(health_router)
    app.include_router(chat_router)
    app.include_router(conversations_router)
    return app


app = create_app()
