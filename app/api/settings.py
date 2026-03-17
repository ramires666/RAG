from fastapi import APIRouter

from app.models.schemas import SettingsStatus
from app.services.lightrag_service import LightRAGService


router = APIRouter(prefix="/settings", tags=["settings"])
lightrag_service = LightRAGService()


@router.get("/status", response_model=SettingsStatus)
async def settings_status() -> SettingsStatus:
    return lightrag_service.settings_status()
