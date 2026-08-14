from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Generic, TypeVar

from app.domain.enums import AgentName
from app.domain.schemas import IncidentRecord, TraceStep

T = TypeVar("T")


class Agent(ABC, Generic[T]):
    name: AgentName

    async def run(self, incident: IncidentRecord) -> tuple[T, TraceStep]:
        step = TraceStep(
            agent=self.name,
            action=self.action_name,
            status="running",
            rationale=self.start_rationale(incident),
        )
        try:
            result = await self.execute(incident)
            step.status = "completed"
            step.finished_at = datetime.now(timezone.utc)
            return result, step
        except Exception:
            step.status = "failed"
            step.finished_at = datetime.now(timezone.utc)
            raise

    @property
    @abstractmethod
    def action_name(self) -> str: ...

    @abstractmethod
    def start_rationale(self, incident: IncidentRecord) -> str: ...

    @abstractmethod
    async def execute(self, incident: IncidentRecord) -> T: ...
