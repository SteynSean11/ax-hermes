"""Fail-closed ApexSigma central-memory provider surface.

The provider speaks only to one explicitly configured Gateway endpoint.  It
does not know or accept database namespace identifiers; the Gateway derives
those from the authenticated client and logical workspace.
"""

from __future__ import annotations

import json
import logging
import os
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

from agent.memory_provider import MemoryProvider

logger = logging.getLogger(__name__)

PROVIDER_NAME = "apexsigma_central_memory"
APPROVED_RESOURCE = "hermes.gateway"
SUPPORTED_OPERATIONS = frozenset({"recall", "store"})
_REQUIRED_CONFIG_KEYS = frozenset({
    "endpoint",
    "client_id",
    "credential_ref",
    "workspace",
    "allowed_operations",
    "allowed_resources",
    "namespace_binding",
})
_NAMESPACE_BINDING_KEYS = frozenset({"logical_workspace", "resolution"})
_FORBIDDEN_NAMESPACE_KEYS = frozenset({
    "tenant",
    "tenant_id",
    "workspace_id",
    "palace",
    "palace_id",
    "collection",
    "collection_name",
})
_RESERVED_REQUEST_KEYS = _FORBIDDEN_NAMESPACE_KEYS | frozenset({
    "operation",
    "resource",
    "workspace",
    "namespace_binding",
    "client_id",
})
_ENV_NAME_RE = re.compile(r"^[A-Z][A-Z0-9_]{0,127}$")


@dataclass(frozen=True)
class _ValidatedConfig:
    endpoint: str
    client_id: str
    credential_ref: str
    workspace: str
    allowed_operations: frozenset[str]
    allowed_resources: frozenset[str]


Transport = Callable[[str, dict[str, str], dict[str, Any]], Any]


def _non_empty_atom(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    if not value or any(char.isspace() for char in value) or len(value) > 256:
        return None
    return value


def _validate_config(raw: Any) -> _ValidatedConfig | None:
    """Validate the complete explicit provider contract without side effects."""
    if not isinstance(raw, Mapping) or not _REQUIRED_CONFIG_KEYS.issubset(raw):
        return None

    endpoint = raw.get("endpoint")
    if not isinstance(endpoint, str) or not endpoint or endpoint != endpoint.strip():
        return None
    try:
        parsed = urlsplit(endpoint)
    except ValueError:
        return None
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.netloc
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or any(char.isspace() for char in endpoint)
    ):
        return None

    client_id = _non_empty_atom(raw.get("client_id"))
    credential_ref = raw.get("credential_ref")
    workspace = _non_empty_atom(raw.get("workspace"))
    if (
        client_id is None
        or not isinstance(credential_ref, str)
        or not _ENV_NAME_RE.fullmatch(credential_ref)
        or workspace is None
    ):
        return None

    operations = raw.get("allowed_operations")
    resources = raw.get("allowed_resources")
    if (
        isinstance(operations, (str, bytes))
        or not isinstance(operations, Sequence | set | frozenset)
        or isinstance(resources, (str, bytes))
        or not isinstance(resources, Sequence | set | frozenset)
    ):
        return None
    try:
        operation_values = frozenset(operations)
        resource_values = frozenset(resources)
    except (TypeError, ValueError):
        return None
    if (
        not operation_values
        or not operation_values.issubset(SUPPORTED_OPERATIONS)
        or not resource_values
        or resource_values != {APPROVED_RESOURCE}
        or not all(
            isinstance(value, str) and _non_empty_atom(value)
            for value in operation_values
        )
    ):
        return None

    binding = raw.get("namespace_binding")
    if not isinstance(binding, Mapping):
        return None
    if set(binding) != _NAMESPACE_BINDING_KEYS:
        return None
    if _FORBIDDEN_NAMESPACE_KEYS.intersection(binding):
        return None
    if (
        binding.get("logical_workspace") != workspace
        or binding.get("resolution") != "server-owned"
    ):
        return None

    # Reject storage identity fields even if a caller tries to smuggle them
    # alongside the provider contract. The server owns their resolution.
    if _FORBIDDEN_NAMESPACE_KEYS.intersection(raw):
        return None

    return _ValidatedConfig(
        endpoint=endpoint,
        client_id=client_id,
        credential_ref=credential_ref,
        workspace=workspace,
        allowed_operations=operation_values,
        allowed_resources=resource_values,
    )


def _load_plugin_config() -> dict[str, Any]:
    """Load only the provider's explicit profile-scoped config block."""
    try:
        from hermes_cli.config import load_config

        config = load_config()
        memory = config.get("memory", {})
        provider_config = (
            memory.get(PROVIDER_NAME, {}) if isinstance(memory, Mapping) else {}
        )
        return dict(provider_config) if isinstance(provider_config, Mapping) else {}
    except Exception:
        return {}


class ApexSigmaCentralMemoryProvider(MemoryProvider):
    """Gateway-mediated central memory with local fail-closed policy checks."""

    def __init__(
        self,
        config: Mapping[str, Any] | None = None,
        *,
        transport: Transport | None = None,
    ) -> None:
        self._config = dict(config) if config is not None else _load_plugin_config()
        self._transport = transport
        self._session_id = ""

    @property
    def name(self) -> str:
        return PROVIDER_NAME

    def _validated_config(self) -> _ValidatedConfig | None:
        try:
            return _validate_config(self._config)
        except Exception:
            # Configuration parsing is a gate, never a reason to activate.
            return None

    @staticmethod
    def _resolve_credential(config: _ValidatedConfig) -> str | None:
        credential = os.environ.get(config.credential_ref, "")
        return credential if credential else None

    def is_available(self) -> bool:
        """Check explicit config and credential presence without network I/O."""
        config = self._validated_config()
        return config is not None and self._resolve_credential(config) is not None

    def get_config_schema(self) -> list[dict[str, Any]]:
        """Describe the explicit contract; no endpoint or URL is defaulted."""
        return [
            {
                "key": "endpoint",
                "description": "Explicit approved Gateway memory API endpoint; no default is provided.",
                "required": True,
            },
            {
                "key": "client_id",
                "description": "Stable server-assigned client identity bound to the credential.",
                "required": True,
            },
            {
                "key": "credential_ref",
                "description": "Environment variable name holding the bearer credential; the value is never stored here.",
                "required": True,
            },
            {
                "key": "workspace",
                "description": "Logical workspace selector; storage namespace IDs are never accepted.",
                "required": True,
            },
            {
                "key": "allowed_operations",
                "description": "Explicit subset of the approved recall/store operations.",
                "required": True,
            },
            {
                "key": "allowed_resources",
                "description": "Explicit approved resource set; must contain only hermes.gateway.",
                "required": True,
            },
            {
                "key": "namespace_binding",
                "description": "Server-owned binding marker for the configured logical workspace.",
                "required": True,
            },
        ]

    def initialize(self, session_id: str, **kwargs: Any) -> None:
        del kwargs
        self._session_id = session_id

    def get_tool_schemas(self) -> list[dict[str, Any]]:
        # This provider is context-only. It adds no model-facing tool surface.
        return []

    def prefetch(self, query: str, *, session_id: str = "") -> str:
        del session_id
        if not query or not query.strip():
            return ""
        response = self.request("recall", {"query": query.strip()})
        context = response.get("context") if isinstance(response, Mapping) else None
        return context if isinstance(context, str) else ""

    def sync_turn(
        self,
        user_content: str,
        assistant_content: str,
        *,
        session_id: str = "",
        messages: list[dict[str, Any]] | None = None,
    ) -> None:
        del session_id, messages
        if not user_content.strip() and not assistant_content.strip():
            return
        self.request(
            "store",
            {
                "user_content": user_content,
                "assistant_content": assistant_content,
            },
        )

    def request(
        self,
        operation: str,
        payload: Mapping[str, Any],
        *,
        resource: str = APPROVED_RESOURCE,
    ) -> Mapping[str, Any] | None:
        """Send one approved envelope, or return None without making a request."""
        config = self._validated_config()
        if config is None:
            return None
        if (
            operation not in SUPPORTED_OPERATIONS
            or operation not in config.allowed_operations
        ):
            return None
        if resource != APPROVED_RESOURCE or resource not in config.allowed_resources:
            return None
        if not isinstance(payload, Mapping) or _RESERVED_REQUEST_KEYS.intersection(
            payload
        ):
            return None

        credential = self._resolve_credential(config)
        if credential is None:
            return None
        body = {
            "operation": operation,
            "resource": resource,
            "workspace": config.workspace,
            **dict(payload),
        }
        headers = {
            "Authorization": f"Bearer {credential}",
            "Content-Type": "application/json",
        }
        try:
            response = (
                self._transport(config.endpoint, headers, body)
                if self._transport is not None
                else self._http_post(config.endpoint, headers, body)
            )
            status_code = getattr(response, "status_code", None)
            if not isinstance(status_code, int) or not 200 <= status_code < 300:
                return None
            data = response.json()
            return dict(data) if isinstance(data, Mapping) else None
        except Exception:
            # Do not expose exception text: it may contain endpoint or bearer data.
            logger.debug("ApexSigma central-memory request failed")
            return None

    @staticmethod
    def _http_post(endpoint: str, headers: dict[str, str], body: dict[str, Any]) -> Any:
        import httpx

        return httpx.post(endpoint, headers=headers, json=body, timeout=10.0)

    def system_prompt_block(self) -> str:
        return ""

    def shutdown(self) -> None:
        return None


def register(ctx: Any) -> None:
    """Register through Hermes' existing memory-provider plugin surface."""
    ctx.register_memory_provider(ApexSigmaCentralMemoryProvider())
