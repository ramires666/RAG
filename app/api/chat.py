from fastapi import APIRouter, HTTPException

from app.models.schemas import AskRequest, AskResponse
from app.services.lightrag_service import LightRAGService
from app.services.router import QueryRouter


router = APIRouter(tags=["chat"])
query_router = QueryRouter()
lightrag_service = LightRAGService()


@router.post("/ask", response_model=AskResponse)
async def ask(request: AskRequest) -> AskResponse:
    if request.scope == "book" and not request.book_id:
        raise HTTPException(status_code=400, detail="book_id is required")

    mode_used = request.mode
    if request.mode == "auto":
        mode_used = await query_router.route(request.question)

    if request.scope == "global":
        return await lightrag_service.query_global(
            question=request.question,
            mode=mode_used,
            requested_mode=request.mode,
        )

    return await lightrag_service.query(
        question=request.question,
        mode=mode_used,
        requested_mode=request.mode,
        book_id=request.book_id,
    )
