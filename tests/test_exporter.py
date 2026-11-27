import json
import re

import pytest

from claude_usage_exporter import __version__
from claude_usage_exporter.exporter import Cache, Config, ShapeError, parse_usage, render


def samples(text):
    """{'name{labels}': value} for every sample line."""
    out = {}
    for line in text.splitlines():
        if line and not line.startswith("#"):
            key, value = line.rsplit(" ", 1)
            out[key] = float(value)
    return out


def cfg_for(creds, url="http://127.0.0.1:9/unused"):
    return Config(credentials=str(creds), url=url)


def test_fixture_renders_expected_samples(creds, usage_doc):
    s = samples(render(cfg_for(creds), fetcher=lambda cfg: usage_doc))
    assert s["claude_usage_up"] == 1
    assert s['claude_usage_percent{window="seven_day"}'] == 42
    assert s['claude_usage_percent{window="five_hour"}'] == 12
    assert s['claude_usage_resets_at_seconds{window="seven_day"}'] == pytest.approx(1894284000.123456)
    assert s['claude_usage_limit_percent{kind="weekly_all",group="weekly",scope="",active="true"}'] == 42
    assert (
        s['claude_usage_limit_percent{kind="weekly_scoped",group="weekly",scope="Opus",active="false"}'] == 9
    )
    assert s["claude_usage_extra_utilization"] == 0
    assert s["claude_cli_credentials_readable"] == 1
    assert s["claude_cli_oauth_access_expires_at_seconds"] == 1893456000
    assert s["claude_cli_oauth_refresh_expires_at_seconds"] == 1896048000
    assert "claude_cli_credentials_mtime_seconds" in s
    assert s[f'claude_usage_exporter_build_info{{version="{__version__}"}}'] == 1
    # extra_usage is its own metric, never a window; null windows are skipped
    assert not any('window="extra_usage"' in k or 'window="seven_day_opus"' in k for k in s)


def test_output_is_valid_exposition(creds, usage_doc):
    text = render(cfg_for(creds), fetcher=lambda cfg: usage_doc)
    sample = re.compile(r'^[a-z_]+(\{([a-z_]+="[^"]*",?)+\})? -?[0-9.e+]+$')
    seen_types = set()
    for line in text.splitlines():
        if line.startswith("# TYPE "):
            name = line.split()[2]
            assert name not in seen_types, f"duplicate TYPE for {name}"
            seen_types.add(name)
        elif not line.startswith("# HELP "):
            assert sample.match(line), line


def test_token_never_in_output(creds, usage_doc):
    text = render(cfg_for(creds), fetcher=lambda cfg: usage_doc)
    assert "FAKE-TEST-TOKEN" not in text


def test_schema_drift_unknown_fields_are_ignored(creds, usage_doc):
    usage_doc["brand_new_top_level"] = {"something": [1, 2, 3]}
    usage_doc["another_codename"] = None
    usage_doc["flag"] = True
    usage_doc["seven_day"]["new_inner_field"] = {"nested": "x"}
    usage_doc["limits"][0]["new_limit_field"] = [1]
    usage_doc["limits"][0]["scope"] = "a string now"
    usage_doc["limits"].append({"kind": "future", "percent": "n/a"})  # non-numeric: skipped
    usage_doc["extra_usage"]["utilization"] = None
    usage_doc["seven_day_future"] = {"utilization": 7, "resets_at": "not a date"}
    s = samples(render(cfg_for(creds), fetcher=lambda cfg: usage_doc))
    assert s["claude_usage_up"] == 1
    assert s['claude_usage_percent{window="seven_day"}'] == 42
    # a new window appears as a new label value, without a reset time it can't parse
    assert s['claude_usage_percent{window="seven_day_future"}'] == 7
    assert 'claude_usage_resets_at_seconds{window="seven_day_future"}' not in s
    assert s['claude_usage_limit_percent{kind="weekly_all",group="weekly",scope="",active="true"}'] == 42
    assert not any('kind="future"' in k for k in s)
    assert "claude_usage_extra_utilization" not in s


@pytest.mark.parametrize(
    "doc",
    [
        [],
        "maintenance",
        None,
        {"limits": "weekly"},
        {"seven_day": {"utilization": 1}, "limits": ["x"]},
        {"seven_day": {"utilization": 1}, "extra_usage": 3},
        {"error": {"type": "not_found", "message": "gone"}},
    ],
)
def test_bad_shape_reports_down(creds, doc, capsys):
    with pytest.raises(ShapeError):
        parse_usage(doc)
    s = samples(render(cfg_for(creds), fetcher=lambda cfg: doc))
    assert s["claude_usage_up"] == 0
    assert not any(k.startswith("claude_usage_percent{") for k in s)
    assert s["claude_cli_credentials_readable"] == 1  # login health is still reported
    assert "unexpected usage response shape" in capsys.readouterr().err


def test_fetch_error_reports_down_without_leaking(creds, capsys):
    def boom(cfg):
        raise OSError("Bearer access-FAKE-TEST-TOKEN rejected")

    s = samples(render(cfg_for(creds), fetcher=boom))
    assert s["claude_usage_up"] == 0
    err = capsys.readouterr().err
    assert "usage fetch failed: OSError" in err
    assert "FAKE" not in err


def test_missing_credentials(tmp_path, usage_doc):
    s = samples(render(cfg_for(tmp_path / "nope.json")))  # real fetch: no token, so down
    assert s["claude_cli_credentials_readable"] == 0
    assert s["claude_usage_up"] == 0
    assert "claude_cli_credentials_mtime_seconds" not in s


def test_malformed_credentials(tmp_path):
    path = tmp_path / "c.json"
    path.write_text(json.dumps({"claudeAiOauth": "x"}))
    s = samples(render(cfg_for(path)))
    assert s["claude_cli_credentials_readable"] == 0
    assert s["claude_usage_up"] == 0


def test_cache(creds, usage_doc):
    calls = []
    now = [100.0]

    def fetcher(cfg):
        calls.append(1)
        return usage_doc

    cache = Cache(Config(credentials=str(creds), cache_seconds=300), fetcher, clock=lambda: now[0])
    cache.get()
    now[0] += 299
    cache.get()
    assert len(calls) == 1
    now[0] += 1
    cache.get()
    assert len(calls) == 2


def test_fetch_sends_token_and_beta_header(creds, upstream):
    s = samples(render(cfg_for(creds, upstream.url)))
    assert s["claude_usage_up"] == 1
    headers = {k.lower(): v for k, v in upstream.requests[0]["headers"].items()}
    assert headers["authorization"] == "Bearer access-FAKE-TEST-TOKEN"
    assert headers["anthropic-beta"] == "oauth-2025-04-20"
    assert headers["user-agent"] == f"claude-usage-exporter/{__version__}"


@pytest.mark.parametrize("status,body", [(401, b'{"error":"unauthorized"}'), (200, b"<html>")])
def test_upstream_http_error_or_garbage(creds, upstream, status, body):
    upstream.status, upstream.body = status, body
    assert samples(render(cfg_for(creds, upstream.url)))["claude_usage_up"] == 0
