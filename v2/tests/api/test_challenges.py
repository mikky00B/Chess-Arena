from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from fastapi.testclient import TestClient

from app.api.challenges import get_challenge_service
from app.core.database import get_session
from app.main import create_app
from app.models import Challenge, ChallengeStatus, DepositRole, EscrowDeposit, StakeAssetType


class FakeSession:
    def add(self, _entity: Any) -> None:
        return None

    async def flush(self) -> None:
        return None

    async def commit(self) -> None:
        return None

    async def refresh(self, _entity: Any) -> None:
        return None


class FakeChallengeService:
    def __init__(self) -> None:
        self.challenge = Challenge(
            id=uuid4(),
            creator_id=uuid4(),
            opponent_id=None,
            game_id=None,
            status=ChallengeStatus.CREATED,
            stake_asset_type=StakeAssetType.NATIVE,
            stake_token_address=None,
            stake_amount=100,
            chain_id=8453,
            escrow_contract_address="0xescrow",
            creator_wallet_address="0xwhite",
            opponent_wallet_address=None,
            created_at=datetime.now(UTC),
            accepted_at=None,
            funded_at=None,
            expires_at=None,
            settled_at=None,
        )

    async def create_challenge(self, *_args: Any, **_kwargs: Any) -> Challenge:
        return self.challenge

    async def verify_deposit(self, *_args: Any, **_kwargs: Any) -> EscrowDeposit:
        return EscrowDeposit(
            id=uuid4(),
            challenge_id=self.challenge.id,
            user_id=self.challenge.creator_id,
            role=DepositRole.WHITE,
            wallet_address="0xwhite",
            tx_hash="0xtx",
            chain_id=8453,
            token_address=None,
            amount=100,
            escrow_contract_address="0xescrow",
            verified=True,
            verified_at=datetime.now(UTC),
            created_at=datetime.now(UTC),
        )


def make_client(service: FakeChallengeService) -> TestClient:
    app = create_app()

    async def override_session() -> AsyncIterator[FakeSession]:
        yield FakeSession()

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_challenge_service] = lambda: service
    return TestClient(app)


def test_create_challenge_endpoint() -> None:
    service = FakeChallengeService()
    client = make_client(service)

    response = client.post(
        "/api/challenges",
        json={
            "creator_id": str(service.challenge.creator_id),
            "creator_wallet_address": "0xwhite",
            "stake_asset_type": "NATIVE",
            "stake_amount": 100,
            "chain_id": 8453,
            "escrow_contract_address": "0xescrow",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == ChallengeStatus.CREATED
    assert body["stake_amount"] == 100


def test_verify_deposit_endpoint_returns_verified_deposit() -> None:
    service = FakeChallengeService()
    client = make_client(service)

    response = client.post(
        f"/api/challenges/{service.challenge.id}/verify-deposit",
        json={
            "user_id": str(service.challenge.creator_id),
            "role": "WHITE",
            "wallet_address": "0xwhite",
            "tx_hash": "0xtx",
            "chain_id": 8453,
            "escrow_contract_address": "0xescrow",
            "amount": 100,
        },
    )

    assert response.status_code == 200
    assert response.json()["verified"] is True
