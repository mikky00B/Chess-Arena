from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.models import SecurityEventSeverity, SettlementRequest, SettlementStatus
from app.services.security_service import SecurityService
from app.services.settlement_service import (
    SettlementExecutionVerification,
    SettlementNotFoundError,
    SettlementService,
    SettlementServiceError,
)

router = APIRouter(prefix="/api/settlements", tags=["settlements"])
SessionDependency = Annotated[AsyncSession, Depends(get_session)]


class SettlementResponse(BaseModel):
    id: UUID
    source_id: UUID
    game_id: UUID
    status: SettlementStatus
    result: str
    winner_id: UUID | None
    amount: int
    recipient_address: str | None
    payload_hash: str
    multisig_tx_hash: str | None
    executed_tx_hash: str | None
    created_at: datetime
    approved_at: datetime | None
    executed_at: datetime | None


class ApproveSettlementRequest(BaseModel):
    multisig_tx_hash: str = Field(min_length=1)


class VerifyExecutionRequest(BaseModel):
    executed_tx_hash: str = Field(min_length=1)
    sender_address: str = Field(min_length=1)
    expected_multisig_address: str = Field(min_length=1)


def get_settlement_service() -> SettlementService:
    return SettlementService()


def get_security_service() -> SecurityService:
    return SecurityService()


SettlementServiceDependency = Annotated[SettlementService, Depends(get_settlement_service)]
SecurityServiceDependency = Annotated[SecurityService, Depends(get_security_service)]


def serialize_settlement(settlement: SettlementRequest) -> SettlementResponse:
    return SettlementResponse(
        id=settlement.id,
        source_id=settlement.source_id,
        game_id=settlement.game_id,
        status=settlement.status,
        result=settlement.result,
        winner_id=settlement.winner_id,
        amount=settlement.amount,
        recipient_address=settlement.recipient_address,
        payload_hash=settlement.payload_hash,
        multisig_tx_hash=settlement.multisig_tx_hash,
        executed_tx_hash=settlement.executed_tx_hash,
        created_at=settlement.created_at,
        approved_at=settlement.approved_at,
        executed_at=settlement.executed_at,
    )


def settlement_error_to_http(exc: Exception) -> HTTPException:
    if isinstance(exc, SettlementNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("", response_model=list[SettlementResponse])
async def list_settlements(
    session: SessionDependency,
    service: SettlementServiceDependency,
) -> list[SettlementResponse]:
    settlements = await service.list_settlements(session)
    return [serialize_settlement(settlement) for settlement in settlements]


@router.get("/{settlement_id}", response_model=SettlementResponse)
async def get_settlement(
    settlement_id: UUID,
    session: SessionDependency,
    service: SettlementServiceDependency,
) -> SettlementResponse:
    try:
        settlement = await service.get_settlement(session, settlement_id=settlement_id)
    except SettlementServiceError as exc:
        raise settlement_error_to_http(exc) from exc
    return serialize_settlement(settlement)


@router.post("/{settlement_id}/approve", response_model=SettlementResponse)
async def approve_settlement(
    http_request: Request,
    settlement_id: UUID,
    request: ApproveSettlementRequest,
    session: SessionDependency,
    service: SettlementServiceDependency,
    security_service: SecurityServiceDependency,
) -> SettlementResponse:
    try:
        settlement = await service.approve_settlement(
            session,
            settlement_id=settlement_id,
            multisig_tx_hash=request.multisig_tx_hash,
        )
        await session.commit()
        await session.refresh(settlement)
        await security_service.log_request_event(
            session,
            http_request,
            event_type="settlement_approved",
            severity=SecurityEventSeverity.WARNING,
            resource_type="settlement",
            resource_id=str(settlement_id),
            metadata={"multisig_tx_hash": request.multisig_tx_hash},
        )
        await session.commit()
    except SettlementServiceError as exc:
        raise settlement_error_to_http(exc) from exc
    return serialize_settlement(settlement)


@router.post("/{settlement_id}/verify-execution", response_model=SettlementResponse)
async def verify_execution(
    http_request: Request,
    settlement_id: UUID,
    request: VerifyExecutionRequest,
    session: SessionDependency,
    service: SettlementServiceDependency,
    security_service: SecurityServiceDependency,
) -> SettlementResponse:
    try:
        settlement = await service.verify_execution(
            session,
            settlement_id=settlement_id,
            verification=SettlementExecutionVerification(
                executed_tx_hash=request.executed_tx_hash,
                sender_address=request.sender_address,
                expected_multisig_address=request.expected_multisig_address,
            ),
        )
        await session.commit()
        await session.refresh(settlement)
        await security_service.log_request_event(
            session,
            http_request,
            event_type="settlement_execution_verified",
            severity=SecurityEventSeverity.WARNING,
            resource_type="settlement",
            resource_id=str(settlement_id),
            metadata={
                "executed_tx_hash": request.executed_tx_hash,
                "sender_address": request.sender_address,
            },
        )
        await session.commit()
    except SettlementServiceError as exc:
        raise settlement_error_to_http(exc) from exc
    return serialize_settlement(settlement)
