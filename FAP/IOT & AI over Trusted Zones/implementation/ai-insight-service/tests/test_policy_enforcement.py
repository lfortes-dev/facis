"""Tests for policy enforcement behavior."""

import pytest

from src.config import PolicyConfig
from src.security.policy import AccessContext, PolicyDeniedError, PolicyEnforcer


def test_policy_denies_missing_agreement() -> None:
    enforcer = PolicyEnforcer(PolicyConfig())
    context = AccessContext(agreement_id="", asset_id="asset-7", roles=("ai_insight_consumer",))
    with pytest.raises(PolicyDeniedError):
        enforcer.enforce(context)


def test_policy_denies_when_required_role_missing() -> None:
    enforcer = PolicyEnforcer(PolicyConfig(required_roles=["ai_insight_consumer"]))
    context = AccessContext(agreement_id="agreement-1", asset_id="asset-7", roles=("viewer",))
    with pytest.raises(PolicyDeniedError):
        enforcer.enforce(context)


def test_policy_allows_matching_role() -> None:
    enforcer = PolicyEnforcer(PolicyConfig(required_roles=["ai_insight_consumer"]))
    context = AccessContext(
        agreement_id="agreement-1",
        asset_id="asset-7",
        roles=("viewer", "ai_insight_consumer"),
    )
    enforcer.enforce(context)
