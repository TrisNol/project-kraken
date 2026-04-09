from __future__ import annotations

import hashlib
from dataclasses import dataclass
from threading import Lock

from haystack.components.generators.utils import print_streaming_chunk

from src.agents import SoftwareDeveloperAgent
from src.core.auth.models import OAuthProvider
from src.core.auth.oauth_service import OAuthService
from src.tools.mcp_oauth_tools import create_oauth_mcp_toolset


@dataclass
class _SessionAgentEntry:
    signature: str
    agent: SoftwareDeveloperAgent
    toolsets: list


class SessionAgentManager:
    def __init__(
        self,
        oauth_service: OAuthService,
        llm_generator_factory,
        is_dev: bool,
    ):
        self._oauth_service = oauth_service
        self._llm_generator_factory = llm_generator_factory
        self._is_dev = is_dev
        self._lock = Lock()
        self._agents: dict[str, _SessionAgentEntry] = {}

    async def get_or_create_agent(self, session_id: str) -> SoftwareDeveloperAgent:
        provider_tokens: list[tuple[OAuthProvider, str]] = []
        for provider in OAuthProvider:
            token = await self._oauth_service.get_valid_access_token(session_id, provider)
            if token:
                provider_tokens.append((provider, token))

        signature = self._signature(provider_tokens)

        with self._lock:
            existing = self._agents.get(session_id)
            if existing and existing.signature == signature:
                return existing.agent

        toolsets = [
            create_oauth_mcp_toolset(provider, token)
            for provider, token in provider_tokens
        ]

        agent = SoftwareDeveloperAgent(
            chat_generator=self._llm_generator_factory(),
            tools=toolsets,
            streaming_callback=print_streaming_chunk if self._is_dev else None,
        )

        with self._lock:
            old_entry = self._agents.get(session_id)
            self._agents[session_id] = _SessionAgentEntry(
                signature=signature,
                agent=agent,
                toolsets=toolsets,
            )

        if old_entry:
            self._close_toolsets(old_entry.toolsets)

        return agent

    def clear_session(self, session_id: str) -> None:
        with self._lock:
            entry = self._agents.pop(session_id, None)
        if entry:
            self._close_toolsets(entry.toolsets)

    def clear_all(self) -> None:
        with self._lock:
            entries = list(self._agents.values())
            self._agents.clear()
        for entry in entries:
            self._close_toolsets(entry.toolsets)

    @staticmethod
    def _signature(provider_tokens: list[tuple[OAuthProvider, str]]) -> str:
        if not provider_tokens:
            return "empty"

        payload = "|".join(
            f"{provider.value}:{hashlib.sha256(token.encode('utf-8')).hexdigest()}"
            for provider, token in sorted(provider_tokens, key=lambda item: item[0].value)
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @staticmethod
    def _close_toolsets(toolsets: list) -> None:
        for toolset in toolsets:
            try:
                toolset.close()
            except Exception:
                # Ignore close errors during cleanup.
                pass
