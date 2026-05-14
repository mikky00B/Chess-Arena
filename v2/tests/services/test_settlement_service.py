from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.models import SettlementRequest, SettlementSourceType, SettlementStatus, StakeAssetType
from app.services.settlement_service import (
    SettlementExecutionVerification,
    SettlementService,
    SettlementServiceError,
)


class FakeSession:
    def __init__(self, settlement: SettlementRequest) -> None:
        self.settlement = settlement

    async def get(self, model: type[object], entity_id: object) -> object | None:
        if model is SettlementRequest and entity_id == self.settlement.id:
            return self.settlement
        return None

    async def flush(self) -> None:
        return None


def make_settlement() -> SettlementRequest:
    return SettlementRequest(
        id=uuid4(),
        source_type=SettlementSourceType.CHALLENGE,
        source_id=uuid4(),
        game_id=uuid4(),
        status=SettlementStatus.PENDING,
        result="WHITE_WIN",
        winner_id=uuid4(),
        asset_type=StakeAssetType.NATIVE,
        token_address=None,
        amount=200,
        recipient_address="0xwinner",
        payload_hash="0x" + "1" * 64,
        multisig_tx_hash=None,
        executed_tx_hash=None,
        created_at=datetime.now(UTC),
        approved_at=None,
        executed_at=None,
    )


async def test_approve_settlement_records_multisig_transaction() -> None:
    settlement = make_settlement()

    await SettlementService().approve_settlement(
        FakeSession(settlement),
        settlement_id=settlement.id,
        multisig_tx_hash="0xmultisig",
    )

    assert settlement.status == SettlementStatus.APPROVED
    assert settlement.multisig_tx_hash == "0xmultisig"
    assert settlement.approved_at is not None


async def test_verify_execution_requires_multisig_sender() -> None:
    settlement = make_settlement()
    service = SettlementService()

    with pytest.raises(SettlementServiceError, match="multisig"):
        await service.verify_execution(
            FakeSession(settlement),
            settlement_id=settlement.id,
            verification=SettlementExecutionVerification(
                executed_tx_hash="0xexecuted",
                sender_address="0xwrong",
                expected_multisig_address="0xsafe",
            ),
        )

    await service.verify_execution(
        FakeSession(settlement),
        settlement_id=settlement.id,
        verification=SettlementExecutionVerification(
            executed_tx_hash="0xexecuted",
            sender_address="0xSAFE",
            expected_multisig_address="0xsafe",
        ),
    )

    assert settlement.status == SettlementStatus.EXECUTED
    assert settlement.executed_tx_hash == "0xexecuted"
