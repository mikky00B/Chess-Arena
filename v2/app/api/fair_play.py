from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.models import FairPlayReport, Game, SecurityEventSeverity
from app.services.security_service import FairPlayReportService, SecurityService

router = APIRouter(prefix="/api/fair-play", tags=["fair-play"])
SessionDependency = Annotated[AsyncSession, Depends(get_session)]


class CreateFairPlayReportRequest(BaseModel):
    game_id: UUID
    reporter_id: UUID | None = None
    accused_user_id: UUID | None = None
    reason: str = Field(min_length=1, max_length=128)
    details: str | None = None


class FairPlayReportResponse(BaseModel):
    id: UUID
    game_id: UUID
    reporter_id: UUID | None
    accused_user_id: UUID | None
    reason: str
    details: str | None
    status: str
    engine_match_percent: int | None
    created_at: datetime
    reviewed_at: datetime | None


def get_fair_play_report_service() -> FairPlayReportService:
    return FairPlayReportService()


def get_security_service() -> SecurityService:
    return SecurityService()


FairPlayReportServiceDependency = Annotated[
    FairPlayReportService,
    Depends(get_fair_play_report_service),
]
SecurityServiceDependency = Annotated[SecurityService, Depends(get_security_service)]


def serialize_report(report: FairPlayReport) -> FairPlayReportResponse:
    return FairPlayReportResponse(
        id=report.id,
        game_id=report.game_id,
        reporter_id=report.reporter_id,
        accused_user_id=report.accused_user_id,
        reason=report.reason,
        details=report.details,
        status=report.status.value,
        engine_match_percent=report.engine_match_percent,
        created_at=report.created_at,
        reviewed_at=report.reviewed_at,
    )


@router.post("/reports", response_model=FairPlayReportResponse, status_code=status.HTTP_201_CREATED)
async def create_report(
    http_request: Request,
    request: CreateFairPlayReportRequest,
    session: SessionDependency,
    service: FairPlayReportServiceDependency,
    security_service: SecurityServiceDependency,
) -> FairPlayReportResponse:
    game = await session.get(Game, request.game_id)
    if game is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="game not found")

    report = await service.create_report(
        session,
        game_id=request.game_id,
        reporter_id=request.reporter_id,
        accused_user_id=request.accused_user_id,
        reason=request.reason,
        details=request.details,
    )
    await session.commit()
    await session.refresh(report)
    await security_service.log_request_event(
        session,
        http_request,
        event_type="fair_play_report_created",
        severity=SecurityEventSeverity.WARNING,
        user_id=request.reporter_id,
        resource_type="game",
        resource_id=str(request.game_id),
        metadata={"report_id": str(report.id), "reason": request.reason},
    )
    await session.commit()
    return serialize_report(report)
