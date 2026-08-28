import asyncio
from collections.abc import Awaitable, Callable
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from rpg_engine_api.controllers.simple_npc import SimpleNpcController


class ExternalDecisionStatus(StrEnum):
    ACCEPTED = "accepted"
    FALLBACK = "fallback"


class VisibleControllerContext(BaseModel):
    schema_version: str = "1.0"
    actor_id: str
    campaign_id: str
    visible_state: dict[str, Any] = Field(default_factory=dict)
    available_actions: tuple[dict[str, Any], ...]
    controller_version: str


class ControllerIntent(BaseModel):
    schema_version: str = "1.0"
    action_id: str
    target_id: str | None = None
    client_reason: str | None = None


class ControllerDecisionTrace(BaseModel):
    schema_version: str = "1.0"
    status: ExternalDecisionStatus
    action: dict[str, Any]
    provider_id: str
    provider_version: str
    fallback_reason: str | None = None


ProviderCallable = Callable[[VisibleControllerContext], Awaitable[ControllerIntent | dict[str, Any]]]


class ExternalControllerAdapter:
    """Timeout-bounded external intent adapter. It never grants rules authority to the provider."""

    def __init__(self, provider_id: str, provider_version: str, provider: ProviderCallable, *, timeout_seconds: float = 2.0, failure_threshold: int = 3) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if failure_threshold <= 0:
            raise ValueError("failure_threshold must be positive")
        self.provider_id = provider_id
        self.provider_version = provider_version
        self.provider = provider
        self.timeout_seconds = timeout_seconds
        self.failure_threshold = failure_threshold
        self.consecutive_failures = 0
        self.circuit_open = False

    async def choose_action(self, context: VisibleControllerContext) -> ControllerDecisionTrace:
        if self.circuit_open:
            return self._fallback(context, "circuit_open")
        try:
            raw = await asyncio.wait_for(self.provider(context), timeout=self.timeout_seconds)
            intent = raw if isinstance(raw, ControllerIntent) else ControllerIntent.model_validate(raw)
            action = self._resolve_intent(intent, context.available_actions)
        except TimeoutError:
            return self._failed(context, "timeout")
        except (ValueError, TypeError) as exc:
            return self._failed(context, f"invalid_output:{type(exc).__name__}")
        except Exception as exc:  # provider errors are isolated from authoritative runtime
            return self._failed(context, f"provider_error:{type(exc).__name__}")
        self.consecutive_failures = 0
        return ControllerDecisionTrace(status=ExternalDecisionStatus.ACCEPTED, action=action, provider_id=self.provider_id, provider_version=self.provider_version)

    def _resolve_intent(self, intent: ControllerIntent, available: tuple[dict[str, Any], ...]) -> dict[str, Any]:
        matches = [dict(action) for action in available if str(action.get("action_id")) == intent.action_id and (intent.target_id is None or str(action.get("target_id")) == intent.target_id)]
        if not matches:
            raise ValueError("external intent did not match an advertised legal action")
        matches.sort(key=lambda action: (str(action.get("action_id", "")), str(action.get("target_id", ""))))
        return matches[0]

    def _failed(self, context: VisibleControllerContext, reason: str) -> ControllerDecisionTrace:
        self.consecutive_failures += 1
        if self.consecutive_failures >= self.failure_threshold:
            self.circuit_open = True
        return self._fallback(context, reason)

    def _fallback(self, context: VisibleControllerContext, reason: str) -> ControllerDecisionTrace:
        fallback = SimpleNpcController(profile="balanced").choose_action({"actor_id": context.actor_id, "available_actions": list(context.available_actions), **context.visible_state})
        return ControllerDecisionTrace(status=ExternalDecisionStatus.FALLBACK, action=fallback, provider_id=self.provider_id, provider_version=self.provider_version, fallback_reason=reason)

    def reset_circuit(self) -> None:
        self.consecutive_failures = 0
        self.circuit_open = False
