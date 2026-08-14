from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import Any
import asyncio

from app.fault_injection.workflow import WorkflowFault, WorkflowFaultMode

from app.domain.enums import AgentName, ToolRisk
from app.domain.schemas import ToolCallRecord

ToolHandler = Callable[..., Awaitable[Any]]


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, tuple[ToolRisk, ToolHandler]] = {}
        self._faults: dict[str, WorkflowFault] = {}

    def register(self, name: str, risk: ToolRisk, handler: ToolHandler) -> None:
        if name in self._tools:
            raise ValueError(f"Tool already registered: {name}")
        self._tools[name] = (risk, handler)

    async def call(
        self,
        name: str,
        *,
        agent: AgentName,
        arguments: dict[str, Any],
        approved: bool = False,
    ) -> tuple[ToolCallRecord, Any | None]:
        if name not in self._tools:
            raise KeyError(f"Unknown tool: {name}")
        risk, handler = self._tools[name]
        record = ToolCallRecord(
            tool_name=name,
            agent=agent,
            risk=risk,
            arguments=arguments,
            status="started",
        )
        if risk == ToolRisk.HIGH and not approved:
            record.status = "blocked"
            record.error = "Human approval required for high-risk tool"
            record.finished_at = datetime.now(timezone.utc)
            return record, None
        try:
            fault = self._faults.get(name)
            if fault and fault.consume():
                if fault.mode == WorkflowFaultMode.TIMEOUT:
                    await asyncio.sleep(max(0.0, fault.delay_seconds))
                    raise TimeoutError(fault.message)
                if fault.mode == WorkflowFaultMode.ERROR:
                    raise RuntimeError(fault.message)
                if fault.mode == WorkflowFaultMode.EMPTY_RESULT:
                    record.status = "succeeded"
                    record.result_summary = "Injected empty result"
                    return record, None
            result = await handler(**arguments)
            record.status = "succeeded"
            record.result_summary = str(result)[:280]
            return record, result
        except Exception as exc:  # pragma: no cover - defensive audit path
            record.status = "failed"
            record.error = f"{type(exc).__name__}: {exc}"
            return record, None
        finally:
            record.finished_at = datetime.now(timezone.utc)


    def inject_fault(self, fault: WorkflowFault) -> None:
        if fault.tool_name not in self._tools:
            raise KeyError(f"Unknown tool: {fault.tool_name}")
        self._faults[fault.tool_name] = fault

    def clear_fault(self, tool_name: str | None = None) -> None:
        if tool_name is None:
            self._faults.clear()
        else:
            self._faults.pop(tool_name, None)

    def active_faults(self) -> list[dict[str, object]]:
        return [
            {
                "tool_name": fault.tool_name,
                "mode": fault.mode.value,
                "remaining_calls": fault.remaining_calls,
                "delay_seconds": fault.delay_seconds,
                "message": fault.message,
            }
            for fault in self._faults.values()
            if fault.remaining_calls > 0
        ]

    def catalog(self) -> list[dict[str, str]]:
        return [
            {"name": name, "risk": risk.value}
            for name, (risk, _) in sorted(self._tools.items())
        ]
