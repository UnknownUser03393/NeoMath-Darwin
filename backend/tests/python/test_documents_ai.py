from __future__ import annotations

from pathlib import Path

from neomath.ai.fallback import explain_diagnostic
from neomath.ai.qwen_client import QwenClient
from neomath.ai.schemas import validate_intent
from neomath.bridge import NeoMathBridge
from neomath.config import AppConfig
from neomath.documents.migration import migrate_document
from neomath.documents.model import NeoMathDocument
from neomath.documents.repository import DocumentRepository


def test_document_round_trip_does_not_persist_secrets(tmp_path: Path) -> None:
    repository = DocumentRepository(tmp_path)
    document = NeoMathDocument(source="x = 1", title="测试")
    path = repository.save(document)
    loaded = repository.load(path)
    assert loaded.source == "x = 1"
    assert loaded.document_id == document.document_id
    text = path.read_text(encoding="utf-8")
    assert "DASHSCOPE" not in text
    assert "API_KEY" not in text


def test_ai_intent_allowlist() -> None:
    assert validate_intent({"intent": "factor", "confidence": 0.9})["intent"] == "factor"
    try:
        validate_intent({"intent": "rewrite_state", "confidence": 1})
    except ValueError:
        pass
    else:
        raise AssertionError("unsafe intent must be rejected")


def test_offline_qwen_falls_back_to_verified_probe(tmp_path: Path) -> None:
    config = AppConfig(
        data_dir=tmp_path,
        dashscope_base_url="https://example.invalid/v1",
        qwen_model="qwen-plus",
        qwen_api_key=None,
    )
    trace = {
        "result": {
            "diagnostics": [{"status": "root_fault", "message": "solutions_lost"}],
            "activeProbe": {"value": "0", "reason": "lost_solution"},
        }
    }
    result = QwenClient(config).explain(trace)
    assert result["source"] == "local"
    assert "x = 0" in result["text"]
    assert explain_diagnostic(trace) == result["text"]


def test_settings_round_trip_masks_api_key(tmp_path: Path) -> None:
    config = AppConfig(
        data_dir=tmp_path,
        dashscope_base_url="https://example.invalid/v1",
        qwen_model="qwen-plus",
        qwen_api_key=None,
    )
    bridge = NeoMathBridge(config)
    saved = bridge.saveSettings(
        {"qwen_api_key": "sk-test-secret-key", "qwen_model": "qwen-turbo", "autosave_seconds": 20}
    )
    assert saved["ok"]
    assert saved["result"]["qwenConfigured"] is True
    assert saved["result"]["qwenApiKeyMasked"].endswith("-key")
    assert "sk-test-secret-key" not in saved["result"]["qwenApiKeyMasked"]
    assert saved["result"]["qwenModel"] == "qwen-turbo"
    assert saved["result"]["autosaveSeconds"] == 20
    assert bridge.qwen.available is True
    cleared = bridge.saveSettings({"qwen_api_key": ""})
    assert cleared["result"]["qwenConfigured"] is False
    assert bridge.qwen.available is False


def test_offline_intent_compiler_is_conservative(tmp_path: Path) -> None:
    config = AppConfig(
        data_dir=tmp_path,
        dashscope_base_url="https://example.invalid/v1",
        qwen_model="qwen-plus",
        qwen_api_key=None,
    )
    client = QwenClient(config)
    assert client.compile_intent("两边除以 x") == {
        "intent": "divide",
        "target": "current_expression",
        "confidence": 0.7,
        "arguments": {"expression": "x"},
    }
    try:
        client.compile_intent("随便改一改")
    except ValueError:
        pass
    else:
        raise AssertionError("unknown offline commands must not silently become solve")


def test_autosave_and_v0_migration(tmp_path: Path) -> None:
    config = AppConfig(
        data_dir=tmp_path,
        dashscope_base_url="https://example.invalid/v1",
        qwen_model="qwen-plus",
        qwen_api_key=None,
    )
    bridge = NeoMathBridge(config)
    payload = {
        "formatVersion": 1,
        "documentId": "autosave-test",
        "title": "自动保存",
        "source": "x = 1",
    }
    response = bridge.autosaveDocument(payload)
    assert response["ok"]
    assert Path(response["result"]["path"]).read_text(encoding="utf-8")
    migrated = migrate_document({"formatVersion": 0, "steps": ["x = 1", "1 = 1"]})
    assert migrated["source"] == "x = 1\n1 = 1"
    assert migrated["formatVersion"] == 1


def test_bridge_save_open_recent_and_stop(tmp_path: Path) -> None:
    config = AppConfig(
        data_dir=tmp_path,
        dashscope_base_url="https://example.invalid/v1",
        qwen_model="qwen-plus",
        qwen_api_key=None,
    )
    bridge = NeoMathBridge(config)
    path = tmp_path / "round-trip.neomath.json"
    payload = {
        "formatVersion": 1,
        "documentId": "bridge-round-trip",
        "title": "Bridge round trip",
        "source": "2x = 2\nx = 1",
        "path": str(path),
    }

    saved = bridge.saveDocument(payload)
    assert saved["ok"]
    opened = bridge.openDocument({"path": str(path)})
    assert opened["ok"]
    assert opened["result"]["document"]["source"] == payload["source"]
    assert bridge.getRecentDocuments()["result"][0]["path"] == str(path)
    assert bridge.stop() == {"ok": True, "result": {"cancelRequested": True}}
