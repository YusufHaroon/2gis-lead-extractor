"""GET /api/sources - data sources the dashboard can offer."""
from fastapi import APIRouter

from app.collectors.registry import list_sources
from app.models.schemas import SourceInfo

router = APIRouter()


@router.get("", response_model=list[SourceInfo])
def get_sources() -> list[SourceInfo]:
    return list_sources()
