"""CAIA_ANTHROPIC_API_KEY routes batch runs straight to Anthropic (2026-10-21).

What is worth pinning: the tables stay keyed by OpenRouter's ids, only the id on
the wire changes, and a model without a direct id stops the run instead of
being sent under a name Anthropic refuses."""
import pytest
from caia import api_client
from caia.api_client import ConfigError, get_client, wire_model, OPUS, SONNET


def test_without_the_key_nothing_changes(monkeypatch):
    monkeypatch.delenv("CAIA_ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    assert wire_model(OPUS) == OPUS
    assert "openrouter.ai" in str(get_client().base_url)


def test_blank_key_is_no_key(monkeypatch):
    monkeypatch.setenv("CAIA_ANTHROPIC_API_KEY", "  ")
    assert wire_model(SONNET) == SONNET


def test_the_key_sends_anthropic_ids_to_anthropic(monkeypatch):
    monkeypatch.setenv("CAIA_ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    assert wire_model(OPUS) == "claude-opus-5-5"
    assert wire_model(SONNET) == "claude-sonnet-5-5"
    assert str(get_client().base_url).startswith("https://api.anthropic.com")


def test_every_configured_model_has_a_direct_id():
    used = {m for m, _ in api_client.AGENT_MODELS.values()} | {api_client.DEFAULT_MODEL}
    assert used <= set(api_client.DIRECT_MODEL_IDS)


def test_unknown_model_stops_on_the_direct_route(monkeypatch):
    monkeypatch.setenv("CAIA_ANTHROPIC_API_KEY", "sk-ant-test")
    with pytest.raises(ConfigError):
        wire_model("anthropic/claude-haiku-9")


def test_complete_sends_the_direct_id(monkeypatch):
    monkeypatch.setenv("CAIA_ANTHROPIC_API_KEY", "sk-ant-test")
    sent = {}

    class Stop(Exception):
        pass

    def fake_create(client, kwargs, budget_s=None):
        sent.update(kwargs)
        raise Stop

    monkeypatch.setattr(api_client, "_create", fake_create)
    with pytest.raises(Stop):
        api_client.complete("qa", "system", [{"role": "user", "content": "x"}], 100)
    assert sent["model"] == "claude-opus-5-5"
