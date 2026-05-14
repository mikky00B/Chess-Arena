from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from app.models import FairPlayReport, SecurityEvent, SecurityEventSeverity


class SecurityService:
    async def log_event(
        self,
        session: AsyncSession,
        *,
        event_type: str,
        severity: SecurityEventSeverity = SecurityEventSeverity.INFO,
        user_id: UUID | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        request_id: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> SecurityEvent:
        event = SecurityEvent(
            event_type=event_type,
            severity=severity,
            user_id=user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            request_id=request_id,
            ip_address=ip_address,
            user_agent=user_agent,
            metadata_json=json.dumps(metadata, sort_keys=True) if metadata else None,
            created_at=datetime.now(UTC),
        )
        session.add(event)
        await session.flush()
        return event

    async def log_request_event(
        self,
        session: AsyncSession,
        request: Request,
        *,
        event_type: str,
        severity: SecurityEventSeverity = SecurityEventSeverity.INFO,
        user_id: UUID | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> SecurityEvent:
        return await self.log_event(
            session,
            event_type=event_type,
            severity=severity,
            user_id=user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            request_id=getattr(request.state, "request_id", None),
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            metadata=metadata,
        )


class FairPlayReportService:
    async def create_report(
        self,
        session: AsyncSession,
        *,
        game_id: UUID,
        reason: str,
        reporter_id: UUID | None = None,
        accused_user_id: UUID | None = None,
        details: str | None = None,
    ) -> FairPlayReport:
        report = FairPlayReport(
            game_id=game_id,
            reporter_id=reporter_id,
            accused_user_id=accused_user_id,
            reason=reason,
            details=details,
            created_at=datetime.now(UTC),
            reviewed_at=None,
        )
        session.add(report)
        await session.flush()
        return report
