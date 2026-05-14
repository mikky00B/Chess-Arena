from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.games import GameResponse, TimeControlRequest, serialize_game
from app.core.database import get_session
from app.models import (
    Challenge,
    ChallengeStatus,
    DepositRole,
    EscrowDeposit,
    SettlementRequest,
    SettlementStatus,
    StakeAssetType,
)
from app.services.challenge_service import (
    ChallengeNotFoundError,
    ChallengeService,
    ChallengeServiceError,
    DepositVerification,
    DepositVerificationError,
)
from app.services.security_service import SecurityService

router = APIRouter(prefix="/api/challenges", tags=["challenges"])
SessionDependency = Annotated[AsyncSession, Depends(get_session)]


class CreateChallengeRequest(BaseModel):
    creator_id: UUID
    creator_wallet_address: str = Field(min_length=1)
    stake_asset_type: StakeAssetType
    stake_token_address: str | None = None
    stake_amount: int = Field(gt=0)
    chain_id: int
    escrow_contract_address: str = Field(min_length=1)
    expires_at: datetime | None = None


class AcceptChallengeRequest(BaseModel):
    opponent_id: UUID
    opponent_wallet_address: str = Field(min_length=1)
    time_control: TimeControlRequest
    rated: bool = False


class VerifyDepositRequest(BaseModel):
    user_id: UUID
    role: DepositRole
    wallet_address: str = Field(min_length=1)
    tx_hash: str = Field(min_length=1)
    chain_id: int
    escrow_contract_address: str = Field(min_length=1)
    token_address: str | None = None
    amount: int = Field(gt=0)


class ChallengeResponse(BaseModel):
    id: UUID
    creator_id: UUID
    opponent_id: UUID | None
    game_id: UUID | None
    status: ChallengeStatus
    stake_asset_type: StakeAssetType
    stake_token_address: str | None
    stake_amount: int
    chain_id: int
    escrow_contract_address: str
    creator_wallet_address: str
    opponent_wallet_address: str | None
    created_at: datetime
    accepted_at: datetime | None
    funded_at: datetime | None
    expires_at: datetime | None
    settled_at: datetime | None
    game: GameResponse | None = None


class DepositResponse(BaseModel):
    id: UUID
    challenge_id: UUID
    user_id: UUID
    role: DepositRole
    wallet_address: str
    tx_hash: str
    chain_id: int
    token_address: str | None
    amount: int
    escrow_contract_address: str
    verified: bool
    verified_at: datetime | None


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


def get_challenge_service() -> ChallengeService:
    return ChallengeService()


def get_security_service() -> SecurityService:
    return SecurityService()


ChallengeServiceDependency = Annotated[ChallengeService, Depends(get_challenge_service)]
SecurityServiceDependency = Annotated[SecurityService, Depends(get_security_service)]


def serialize_challenge(challenge: Challenge) -> ChallengeResponse:
    return ChallengeResponse(
        id=challenge.id,
        creator_id=challenge.creator_id,
        opponent_id=challenge.opponent_id,
        game_id=challenge.game_id,
        status=challenge.status,
        stake_asset_type=challenge.stake_asset_type,
        stake_token_address=challenge.stake_token_address,
        stake_amount=challenge.stake_amount,
        chain_id=challenge.chain_id,
        escrow_contract_address=challenge.escrow_contract_address,
        creator_wallet_address=challenge.creator_wallet_address,
        opponent_wallet_address=challenge.opponent_wallet_address,
        created_at=challenge.created_at,
        accepted_at=challenge.accepted_at,
        funded_at=challenge.funded_at,
        expires_at=challenge.expires_at,
        settled_at=challenge.settled_at,
        game=serialize_game(challenge.game) if challenge.game else None,
    )


def serialize_deposit(deposit: EscrowDeposit) -> DepositResponse:
    return DepositResponse(
        id=deposit.id,
        challenge_id=deposit.challenge_id,
        user_id=deposit.user_id,
        role=deposit.role,
        wallet_address=deposit.wallet_address,
        tx_hash=deposit.tx_hash,
        chain_id=deposit.chain_id,
        token_address=deposit.token_address,
        amount=deposit.amount,
        escrow_contract_address=deposit.escrow_contract_address,
        verified=deposit.verified,
        verified_at=deposit.verified_at,
    )


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
    )


def challenge_error_to_http(exc: Exception) -> HTTPException:
    if isinstance(exc, ChallengeNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, DepositVerificationError):
        return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("", response_model=ChallengeResponse, status_code=status.HTTP_201_CREATED)
async def create_challenge(
    http_request: Request,
    request: CreateChallengeRequest,
    session: SessionDependency,
    service: ChallengeServiceDependency,
    security_service: SecurityServiceDependency,
) -> ChallengeResponse:
    try:
        challenge = await service.create_challenge(
            session,
            creator_id=request.creator_id,
            creator_wallet_address=request.creator_wallet_address,
            stake_asset_type=request.stake_asset_type,
            stake_token_address=request.stake_token_address,
            stake_amount=request.stake_amount,
            chain_id=request.chain_id,
            escrow_contract_address=request.escrow_contract_address,
            expires_at=request.expires_at,
        )
        await session.commit()
        await session.refresh(challenge)
        await security_service.log_request_event(
            session,
            http_request,
            event_type="challenge_created",
            user_id=request.creator_id,
            resource_type="challenge",
            resource_id=str(challenge.id),
            metadata={"stake_amount": request.stake_amount, "chain_id": request.chain_id},
        )
        await session.commit()
    except ChallengeServiceError as exc:
        raise challenge_error_to_http(exc) from exc
    return serialize_challenge(challenge)


@router.get("", response_model=list[ChallengeResponse])
async def list_challenges(session: SessionDependency) -> list[ChallengeResponse]:
    challenges = (await session.scalars(select(Challenge))).all()
    return [serialize_challenge(challenge) for challenge in challenges]


@router.get("/{challenge_id}", response_model=ChallengeResponse)
async def get_challenge(
    challenge_id: UUID,
    session: SessionDependency,
    service: ChallengeServiceDependency,
) -> ChallengeResponse:
    try:
        challenge = await service.get_challenge(session, challenge_id=challenge_id)
    except ChallengeServiceError as exc:
        raise challenge_error_to_http(exc) from exc
    return serialize_challenge(challenge)


@router.post("/{challenge_id}/accept", response_model=ChallengeResponse)
async def accept_challenge(
    challenge_id: UUID,
    request: AcceptChallengeRequest,
    session: SessionDependency,
    service: ChallengeServiceDependency,
) -> ChallengeResponse:
    try:
        challenge = await service.accept_challenge(
            session,
            challenge_id=challenge_id,
            opponent_id=request.opponent_id,
            opponent_wallet_address=request.opponent_wallet_address,
            time_control=request.time_control.to_domain(),
            rated=request.rated,
        )
        await session.commit()
        await session.refresh(challenge)
    except ChallengeServiceError as exc:
        raise challenge_error_to_http(exc) from exc
    return serialize_challenge(challenge)


@router.post("/{challenge_id}/verify-deposit", response_model=DepositResponse)
async def verify_deposit(
    http_request: Request,
    challenge_id: UUID,
    request: VerifyDepositRequest,
    session: SessionDependency,
    service: ChallengeServiceDependency,
    security_service: SecurityServiceDependency,
) -> DepositResponse:
    try:
        deposit = await service.verify_deposit(
            session,
            challenge_id=challenge_id,
            verification=DepositVerification(
                user_id=request.user_id,
                role=request.role,
                wallet_address=request.wallet_address,
                tx_hash=request.tx_hash,
                chain_id=request.chain_id,
                escrow_contract_address=request.escrow_contract_address,
                token_address=request.token_address,
                amount=request.amount,
            ),
        )
        await session.commit()
        await session.refresh(deposit)
        await security_service.log_request_event(
            session,
            http_request,
            event_type="challenge_deposit_verified",
            user_id=request.user_id,
            resource_type="challenge",
            resource_id=str(challenge_id),
            metadata={"role": request.role.value, "tx_hash": request.tx_hash},
        )
        await session.commit()
    except ChallengeServiceError as exc:
        raise challenge_error_to_http(exc) from exc
    return serialize_deposit(deposit)


@router.post("/{challenge_id}/start", response_model=ChallengeResponse)
async def start_challenge(
    challenge_id: UUID,
    session: SessionDependency,
    service: ChallengeServiceDependency,
) -> ChallengeResponse:
    try:
        challenge = await service.start_funded_challenge(session, challenge_id=challenge_id)
        await session.commit()
        await session.refresh(challenge)
    except ChallengeServiceError as exc:
        raise challenge_error_to_http(exc) from exc
    return serialize_challenge(challenge)


@router.post("/{challenge_id}/cancel", response_model=ChallengeResponse)
async def cancel_challenge(
    challenge_id: UUID,
    session: SessionDependency,
    service: ChallengeServiceDependency,
) -> ChallengeResponse:
    try:
        challenge = await service.cancel_challenge(session, challenge_id=challenge_id)
        await session.commit()
        await session.refresh(challenge)
    except ChallengeServiceError as exc:
        raise challenge_error_to_http(exc) from exc
    return serialize_challenge(challenge)


@router.get("/{challenge_id}/settlement", response_model=SettlementResponse)
async def get_or_create_settlement(
    challenge_id: UUID,
    session: SessionDependency,
    service: ChallengeServiceDependency,
) -> SettlementResponse:
    settlement = await session.scalar(
        select(SettlementRequest).where(SettlementRequest.source_id == challenge_id)
    )
    if settlement is None:
        try:
            settlement = await service.create_settlement_request(
                session,
                challenge_id=challenge_id,
            )
            await session.commit()
            await session.refresh(settlement)
        except ChallengeServiceError as exc:
            raise challenge_error_to_http(exc) from exc
    return serialize_settlement(settlement)
