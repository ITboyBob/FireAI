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


def create_app() -> FastAPI:
    app = FastAPI(title="消防问答系统 2.0")
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/", response_class=HTMLResponse, tags=["web"])
    async def index(request: Request) -> HTMLResponse:
        return TEMPLATES.TemplateResponse(
            request=request,
            name="index.html",
            context={
                "page_title": "消防问答系统 2.0",
                "chat_endpoint": "/api/chat",
                "conversation_endpoint": "/api/conversations",
            },
        )

    app.include_router(health_router)
    app.include_router(chat_router)
    app.include_router(conversations_router)
    return app


app = create_app()
