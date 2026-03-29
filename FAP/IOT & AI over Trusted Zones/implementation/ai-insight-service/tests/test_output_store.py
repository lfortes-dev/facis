"""Tests for AI output storage helpers."""

from src.storage.output_store import InMemoryOutputStore


def test_output_store_save_and_get() -> None:
    store = InMemoryOutputStore()
    record = store.save(
        insight_type="anomaly-report",
        agreement_id="agreement-1",
        asset_id="asset-7",
        input_data={"window": {"rows_analyzed": 10}},
        llm_model="llama-2-7b-chat",
        output_text='{"summary":"ok","key_findings":[],"recommendations":[]}',
        structured_output={"summary": "ok", "key_findings": [], "recommendations": []},
    )
    fetched = store.get(record.id)
    assert fetched is not None
    assert fetched.id == record.id


def test_output_store_latest_for_types() -> None:
    store = InMemoryOutputStore()
    store.save(
        insight_type="energy-summary",
        agreement_id="agreement-1",
        asset_id="asset-7",
        input_data={},
        llm_model="llama-2-7b-chat",
        output_text="{}",
        structured_output={"summary": "ok", "key_findings": [], "recommendations": []},
    )
    latest = store.latest_for_types(("energy-summary", "anomaly-report"))
    assert latest["energy-summary"] is not None
    assert latest["anomaly-report"] is None
