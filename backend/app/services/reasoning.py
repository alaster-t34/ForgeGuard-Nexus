from __future__ import annotations

from typing import Any

import httpx

from app.domain.schemas import AssistantRequest, AssistantResponse


class ReasoningGateway:
    """Local-first reasoning gateway.

    The platform runs fully without a language model. When a local Ollama or
    OpenAI-compatible endpoint is configured, the gateway can improve language
    understanding without sending industrial data to a public cloud service.
    """

    def __init__(self, settings, store) -> None:
        self.settings = settings
        self.store = store

    async def answer(self, request: AssistantRequest) -> AssistantResponse:
        incident = self.store.get_incident(request.incident_id) if request.incident_id else None
        asset = self.store.get_asset(request.asset_id) if request.asset_id else None
        context = self._context(asset, incident)
        if self.settings.reasoning_provider == "local" and self.settings.local_llm_base_url:
            try:
                answer = await self._local_llm(request.query, context)
                return AssistantResponse(
                    answer=answer,
                    reasoning_mode="local-llm-with-governed-context",
                    recommended_actions=self._actions(incident),
                    evidence_ids=[item.id for item in incident.evidence[:8]] if incident else [],
                    safety_notice=("AI 输出仅用于决策支持；生产和维修动作必须由授权人员批准。" if request.language == "zh-CN" else "AI output is decision support. Production and maintenance actions require authorized human approval."),
                )
            except Exception:
                pass
        return AssistantResponse(
            answer=self._deterministic_answer(request.query, asset, incident),
            reasoning_mode="deterministic-domain-reasoning",
            recommended_actions=self._actions(incident),
            evidence_ids=[item.id for item in incident.evidence[:8]] if incident else [],
            safety_notice=("AI 输出仅用于决策支持；生产和维修动作必须由授权人员批准。" if request.language == "zh-CN" else "AI output is decision support. Production and maintenance actions require authorized human approval."),
        )

    async def _local_llm(self, query: str, context: str) -> str:
        base = self.settings.local_llm_base_url.rstrip("/")
        model = self.settings.local_llm_model or "qwen2.5:7b-instruct"
        async with httpx.AsyncClient(timeout=30) as client:
            if base.endswith("/v1"):
                response = await client.post(
                    f"{base}/chat/completions",
                    json={
                        "model": model,
                        "temperature": 0.1,
                        "messages": [
                            {"role": "system", "content": "You are a cautious industrial maintenance copilot. Never authorize equipment control."},
                            {"role": "user", "content": f"Context:\n{context}\n\nQuestion:\n{query}"},
                        ],
                    },
                )
                response.raise_for_status()
                return response.json()["choices"][0]["message"]["content"]
            response = await client.post(
                f"{base}/api/chat",
                json={
                    "model": model,
                    "stream": False,
                    "messages": [
                        {"role": "system", "content": "You are a cautious industrial maintenance copilot. Never authorize equipment control."},
                        {"role": "user", "content": f"Context:\n{context}\n\nQuestion:\n{query}"},
                    ],
                },
            )
            response.raise_for_status()
            return response.json()["message"]["content"]

    @staticmethod
    def _context(asset: Any, incident: Any) -> str:
        parts = []
        if asset:
            parts.append(f"Asset: {asset.name}; health={asset.health_score}; status={asset.status.value}")
        if incident:
            parts.append(f"Incident: {incident.id}; status={incident.status.value}; risk={incident.risk.value}")
            if incident.diagnosis:
                parts.append(f"Diagnosis: {incident.diagnosis.primary.fault_mode}; probability={incident.diagnosis.primary.probability}")
            if incident.reliability:
                parts.append(f"RUL p10/p50/p90={incident.reliability.rul_hours_p10}/{incident.reliability.rul_hours_p50}/{incident.reliability.rul_hours_p90} h")
        return "\n".join(parts) or "No incident or asset selected."

    @staticmethod
    def _actions(incident) -> list[str]:
        if not incident:
            return ["Select an asset or incident", "Review the fleet risk overview"]
        if incident.status.value == "awaiting_approval":
            return ["Review evidence and safety controls", "Compare maintenance options", "Approve, reject or request more evidence"]
        if incident.status.value == "in_progress":
            return ["Complete the work-order checklist", "Capture post-maintenance evidence"]
        if incident.status.value == "resolved":
            return ["Review the before/after evidence package", "Update the maintenance knowledge base"]
        return ["Inspect data quality", "Run the governed agent loop"]

    @staticmethod
    def _deterministic_answer(query: str, asset, incident) -> str:
        q = query.lower()
        if incident:
            if "why" in q or "原因" in query or "为什么" in query:
                hypothesis = incident.diagnosis.primary if incident.diagnosis else None
                return (
                    f"当前主假设为“{hypothesis.fault_mode}”，概率 {hypothesis.probability:.0%}。"
                    f"关键依据是：{hypothesis.rationale} 系统仍保留反证和补采要求，不会直接控制设备。"
                    if hypothesis
                    else "当前事件尚未完成诊断。"
                )
            if "安全" in query or "safe" in q:
                safety = incident.safety
                return (
                    f"人员安全评分 {safety.score:.0f}/100，风险等级 {safety.risk.value}。"
                    f"必须执行：{'；'.join(safety.required_controls[:3])}。"
                    if safety
                    else "安全 Agent 尚未完成评估。"
                )
            if "方案" in query or "plan" in q:
                plan = incident.plan
                if plan:
                    selected = next(item for item in plan.options if item.id == plan.recommended_option_id)
                    return f"推荐方案是“{selected.title}”，综合评分 {selected.score:.1f}。推荐原因：{plan.approval_reason}"
        if asset:
            return f"{asset.name} 当前健康度 {asset.health_score:.0f}/100，状态 {asset.status.value}，中位 RUL 约 {asset.estimated_rul_hours or 0:.0f} 小时。"
        return "请选择资产或事件。ForgeGuard 可解释数据质量、诊断、RUL、安全约束、可持续影响与维修方案，但不会替代授权人员做生产决策。"
