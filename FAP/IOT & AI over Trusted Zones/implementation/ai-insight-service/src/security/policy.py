"""Policy checks for agreement/asset/role-based access."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from src.config import PolicyConfig


class PolicyDeniedError(Exception):
    """Raised when policy checks fail."""


@dataclass(frozen=True)
class AccessContext:
    """Identity and scope values extracted from request headers."""

    agreement_id: str
    asset_id: str
    roles: tuple[str, ...]


class PolicyEnforcer:
    """Header-driven policy enforcement."""

    def __init__(self, config: PolicyConfig) -> None:
        self._config = config

    def build_context(self, headers: Mapping[str, str]) -> AccessContext:
        agreement_id = headers.get(self._config.agreement_header, "").strip()
        asset_id = headers.get(self._config.asset_header, "").strip()
        raw_roles = headers.get(self._config.role_header, "")
        roles = tuple(role.strip() for role in raw_roles.split(",") if role.strip())
        return AccessContext(agreement_id=agreement_id, asset_id=asset_id, roles=roles)

    def enforce(self, context: AccessContext) -> None:
        if not self._config.enabled:
            return
        if not context.agreement_id:
            raise PolicyDeniedError("Missing agreement identifier")
        if not context.asset_id:
            raise PolicyDeniedError("Missing asset identifier")

        if self._config.required_roles:
            required = set(self._config.required_roles)
            present = set(context.roles)
            if required.isdisjoint(present):
                raise PolicyDeniedError("Missing required role")

        if self._config.allowed_agreement_ids:
            allowed_agreements = set(self._config.allowed_agreement_ids)
            if context.agreement_id not in allowed_agreements:
                raise PolicyDeniedError("Agreement is not authorized")

        if self._config.allowed_asset_ids:
            allowed_assets = set(self._config.allowed_asset_ids)
            if context.asset_id not in allowed_assets:
                raise PolicyDeniedError("Asset is not authorized")
