from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse

from app.api.books import router as books_router
from app.api.chat import router as chat_router
from app.api.settings import router as settings_router
from app.config import get_settings


settings = get_settings()
ui_path = Path(__file__).parent / "web" / "index.html"

app = FastAPI(title=settings.app_name)
app.include_router(books_router)
app.include_router(chat_router)
app.include_router(settings_router)


@app.get("/", include_in_schema=False)
async def root() -> FileResponse:
    return FileResponse(ui_path)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "env": settings.app_env}
