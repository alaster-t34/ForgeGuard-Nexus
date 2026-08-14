from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class WorkflowFaultMode(str, Enum):
    ERROR = "error"
    TIMEOUT = "timeout"
    EMPTY_RESULT = "empty_result"


@dataclass(slots=True)
class WorkflowFault:
    tool_name: str
    mode: WorkflowFaultMode
    remaining_calls: int = 1
    delay_seconds: float = 0.05
    message: str = "Injected workflow fault"

    def consume(self) -> bool:
        if self.remaining_calls <= 0:
            return False
        self.remaining_calls -= 1
        return True
