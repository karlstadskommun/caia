"""CAIA_OPENROUTER_REGION picks OpenRouter's entry point (2026-10-08).

The rule worth pinning: a value the code does not know is an error, never the
global route. An operator who set "europe" expecting the EU must find out."""
import pytest
from caia import api_client
from caia.api_client import ConfigError, get_client, openrouter_base_url


@pytest.mark.parametrize("value, url", [
    ("", "https://openrouter.ai/api"),
    ("eu", "https://eu.openrouter.ai/api"),
    (" EU ", "https://eu.openrouter.ai/api"),
    ("us", "https://us.openrouter.ai/api"),
])
def test_known_regions(monkeypatch, value, url):
    monkeypatch.setenv("CAIA_OPENROUTER_REGION", value)
    assert openrouter_base_url() == url


def test_unset_is_global(monkeypatch):
    monkeypatch.delenv("CAIA_OPENROUTER_REGION", raising=False)
    assert openrouter_base_url() == "https://openrouter.ai/api"


@pytest.mark.parametrize("value", ["europe", "eu-west", "se", "global"])
def test_unknown_region_stops_instead_of_going_global(monkeypatch, value):
    monkeypatch.setenv("CAIA_OPENROUTER_REGION", value)
    with pytest.raises(ConfigError):
        openrouter_base_url()


def test_client_uses_the_region(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    monkeypatch.setenv("CAIA_OPENROUTER_REGION", "eu")
    assert str(get_client().base_url).startswith("https://eu.openrouter.ai/api")


def test_client_refuses_an_unknown_region(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    monkeypatch.setenv("CAIA_OPENROUTER_REGION", "europe")
    with pytest.raises(ConfigError):
        get_client()


def test_the_table_has_no_silent_alias():
    # Every key is a value someone would type on purpose; no catch-all.
    assert set(api_client.OPENROUTER_BASE_URLS) == {"", "eu", "us"}
