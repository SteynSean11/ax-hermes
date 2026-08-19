"""Declarative config surface for the ApexSigma central-memory provider."""

from plugins.memory.config_schema import (
    KIND_JSON,
    KIND_TEXT,
    ProviderConfigSchema,
    ProviderField,
    STORAGE_FLAT_JSON,
)


CONFIG_SCHEMA = ProviderConfigSchema(
    name="apexsigma_central_memory",
    label="ApexSigma central memory",
    storage=STORAGE_FLAT_JSON,
    fields=(
        ProviderField(
            key="endpoint",
            label="Gateway memory endpoint",
            kind=KIND_TEXT,
            description="Explicit approved Gateway-mediated memory API endpoint; no default.",
            inline=True,
            group="Connection",
        ),
        ProviderField(
            key="client_id",
            label="Client identity",
            kind=KIND_TEXT,
            description="Stable server-assigned client identity; not sent as a namespace selector.",
            inline=True,
            group="Identity",
        ),
        ProviderField(
            key="credential_ref",
            label="Credential reference",
            kind=KIND_TEXT,
            description="Environment variable name for the bearer credential; never the credential value.",
            inline=True,
            group="Identity",
        ),
        ProviderField(
            key="workspace",
            label="Logical workspace",
            kind=KIND_TEXT,
            description="Logical workspace only; the server resolves storage identifiers.",
            inline=True,
            group="Namespace",
        ),
        ProviderField(
            key="allowed_operations",
            label="Allowed operations",
            kind=KIND_JSON,
            description="JSON list containing only approved recall/store operations.",
            placeholder='["recall", "store"]',
            group="Policy",
        ),
        ProviderField(
            key="allowed_resources",
            label="Allowed resources",
            kind=KIND_JSON,
            description='JSON list containing only "hermes.gateway".',
            placeholder='["hermes.gateway"]',
            group="Policy",
        ),
        ProviderField(
            key="namespace_binding",
            label="Namespace binding",
            kind=KIND_JSON,
            description='JSON object: {"logical_workspace": "...", "resolution": "server-owned"}.',
            placeholder='{"logical_workspace": "workspace-a", "resolution": "server-owned"}',
            group="Namespace",
        ),
    ),
)
