"""Focused tests for the fail-closed ApexSigma central-memory provider."""

from __future__ import annotations

import logging

from plugins.memory.apexsigma_central_memory import (
    APPROVED_RESOURCE,
    ApexSigmaCentralMemoryProvider,
)

TOKEN = "test-only-central-memory-token"


class FakeResponse:
    def __init__(self, payload: object, status_code: int = 200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload


def valid_config(**overrides):
    config = {
        "endpoint": "https://gateway.invalid/memory",
        "client_id": "hermes-wsl",
        "credential_ref": "APEXSIGMA_CENTRAL_MEMORY_TOKEN",
        "workspace": "workspace-a",
        "allowed_operations": ["recall", "store"],
        "allowed_resources": [APPROVED_RESOURCE],
        "namespace_binding": {
            "logical_workspace": "workspace-a",
            "resolution": "server-owned",
        },
    }
    config.update(overrides)
    return config


def make_provider(monkeypatch, transport, **overrides):
    monkeypatch.setenv("APEXSIGMA_CENTRAL_MEMORY_TOKEN", TOKEN)
    return ApexSigmaCentralMemoryProvider(
        valid_config(**overrides), transport=transport
    )


def test_missing_or_invalid_configuration_fails_closed(monkeypatch):
    calls = []
    invalid_configs = [
        {},
        valid_config(endpoint=""),
        valid_config(endpoint="https://[invalid"),
        valid_config(client_id=""),
        valid_config(credential_ref="not an env name"),
        valid_config(workspace=""),
        valid_config(allowed_operations=[]),
        valid_config(allowed_resources=[]),
        valid_config(namespace_binding={"logical_workspace": "workspace-a"}),
        valid_config(
            namespace_binding={
                "logical_workspace": "workspace-a",
                "resolution": "server-owned",
                "palace_id": "must-not-be-client-supplied",
            }
        ),
    ]

    monkeypatch.setenv("APEXSIGMA_CENTRAL_MEMORY_TOKEN", TOKEN)
    for config in invalid_configs:
        provider = ApexSigmaCentralMemoryProvider(
            config,
            transport=lambda *args: calls.append(args),
        )
        assert provider.is_available() is False
        assert provider.prefetch("query") == ""
        provider.sync_turn("user", "assistant")

    assert calls == []


def test_missing_credential_fails_closed_without_request(monkeypatch):
    calls = []
    monkeypatch.delenv("APEXSIGMA_CENTRAL_MEMORY_TOKEN", raising=False)
    provider = ApexSigmaCentralMemoryProvider(
        valid_config(),
        transport=lambda *args: calls.append(args),
    )

    assert provider.is_available() is False
    assert provider.prefetch("query") == ""
    assert calls == []


def test_no_secret_leakage_in_errors_or_logs(monkeypatch, caplog):
    def failing_transport(*args):
        raise RuntimeError(f"Authorization Bearer {TOKEN}")

    provider = make_provider(monkeypatch, failing_transport)
    with caplog.at_level(logging.DEBUG):
        assert provider.prefetch("query") == ""

    assert TOKEN not in caplog.text
    assert "Authorization" not in caplog.text


def test_only_logical_workspace_is_sent(monkeypatch):
    requests = []

    def transport(endpoint, headers, body):
        requests.append((endpoint, headers, body))
        return FakeResponse({"context": "recalled context"})

    provider = make_provider(monkeypatch, transport)
    assert provider.prefetch("remember this") == "recalled context"

    endpoint, headers, body = requests[0]
    assert endpoint == "https://gateway.invalid/memory"
    assert headers["Authorization"] == f"Bearer {TOKEN}"
    assert body == {
        "operation": "recall",
        "resource": APPROVED_RESOURCE,
        "workspace": "workspace-a",
        "query": "remember this",
    }
    assert "client_id" not in body
    assert all(
        key not in body
        for key in ("tenant_id", "workspace_id", "palace_id", "collection_name")
    )


def test_unsupported_operation_or_resource_is_denied_locally(monkeypatch):
    calls = []
    provider = make_provider(
        monkeypatch,
        lambda *args: calls.append(args),
    )

    assert provider.request("delete", {"query": "x"}) is None
    assert provider.request("recall", {"query": "x"}, resource="omega.api") is None
    assert provider.request("recall", {"palace_id": "client-input"}) is None
    assert calls == []


def test_network_failures_fail_closed(monkeypatch):
    def failing_transport(*args):
        raise OSError("network unavailable")

    provider = make_provider(monkeypatch, failing_transport)
    assert provider.is_available() is True
    assert provider.prefetch("query") == ""
    provider.sync_turn("user", "assistant")


def test_registers_with_existing_memory_plugin_context():
    from plugins.memory.apexsigma_central_memory import register

    class Context:
        def __init__(self):
            self.provider = None

        def register_memory_provider(self, provider):
            self.provider = provider

    context = Context()
    register(context)
    assert isinstance(context.provider, ApexSigmaCentralMemoryProvider)
    assert context.provider.get_tool_schemas() == []
