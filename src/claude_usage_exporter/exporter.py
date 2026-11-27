"""Fetch the plan's usage windows and render them as Prometheus text.

The usage endpoint is undocumented (it is what Claude Code's own `/usage` view calls), so the
parser is defensive: fields it doesn't know are ignored, and a response whose shape it can't read
is reported as `claude_usage_up 0` instead of crashing the scrape.

Only timestamps leave the credentials file. Token values are never exported or logged.
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime

from . import __version__

DEFAULT_URL = "https://api.anthropic.com/api/oauth/usage"
OAUTH_BETA = "oauth-2025-04-20"


class ShapeError(ValueError):
    """The usage response doesn't have the shape this exporter understands."""


def log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def parse_ts(value: object) -> float | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def esc(value: object) -> str:
    return str(value).replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


def is_num(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def fmt(value: float) -> str:
    return repr(value) if isinstance(value, float) else str(value)


@dataclass
class Usage:
    windows: dict[str, tuple[float, float | None]] = field(default_factory=dict)
    limits: list[dict[str, object]] = field(default_factory=list)
    extra_utilization: float | None = None


def parse_usage(doc: object) -> Usage:
    """Turn the decoded JSON body into a Usage, or raise ShapeError.

    Windows are the top-level objects that carry a numeric `utilization` (five_hour, seven_day,
    ...); new ones show up as new `window` label values. Top-level nulls and objects without
    `utilization` are ignored, and so are unknown keys inside known objects.
    """
    if not isinstance(doc, dict):
        raise ShapeError(f"top level is {type(doc).__name__}, not an object")
    usage = Usage()
    for name, value in doc.items():
        if name in ("extra_usage", "limits") or not isinstance(value, dict):
            continue
        util = value.get("utilization")
        if is_num(util):
            usage.windows[name] = (util, parse_ts(value.get("resets_at")))

    extra = doc.get("extra_usage")
    if extra is not None:
        if not isinstance(extra, dict):
            raise ShapeError("extra_usage is not an object")
        if is_num(extra.get("utilization")):
            usage.extra_utilization = extra["utilization"]

    limits = doc.get("limits")
    if limits is not None:
        if not isinstance(limits, list):
            raise ShapeError("limits is not a list")
        for item in limits:
            if not isinstance(item, dict):
                raise ShapeError("a limits entry is not an object")
            percent = item.get("percent")
            if not is_num(percent):
                continue
            scope = item.get("scope")
            model = scope.get("model") if isinstance(scope, dict) else None
            name = model.get("display_name") if isinstance(model, dict) else None
            usage.limits.append(
                {
                    "kind": item.get("kind") or "",
                    "group": item.get("group") or "",
                    "scope": name if isinstance(name, str) else "",
                    "active": "true" if item.get("is_active") else "false",
                    "percent": percent,
                }
            )

    if not usage.windows and not usage.limits:
        raise ShapeError("no usage windows or limits in the response")
    return usage


@dataclass
class Config:
    bind: str = "127.0.0.1"
    port: int = 9101
    cache_seconds: int = 300
    credentials: str = "~/.claude/.credentials.json"
    url: str = DEFAULT_URL
    timeout: float = 15.0

    @property
    def credentials_path(self) -> str:
        return os.path.expanduser(self.credentials)


def read_oauth(path: str) -> dict:
    with open(path, encoding="utf-8") as fh:
        oauth = json.load(fh)["claudeAiOauth"]
    if not isinstance(oauth, dict):
        raise ValueError("claudeAiOauth is not an object")
    return oauth


def fetch(cfg: Config) -> object:
    token = read_oauth(cfg.credentials_path)["accessToken"]
    if not isinstance(token, str) or not token:
        raise ValueError("no access token in the credentials file")
    req = urllib.request.Request(
        cfg.url,
        headers={
            "Authorization": "Bearer " + token,
            "anthropic-beta": OAUTH_BETA,
            "Accept": "application/json",
            "User-Agent": f"claude-usage-exporter/{__version__}",
        },
    )
    with urllib.request.urlopen(req, timeout=cfg.timeout) as resp:
        return json.load(resp)


def gauge(out: list[str], name: str, help_: str) -> None:
    out.append(f"# HELP {name} {help_}")
    out.append(f"# TYPE {name} gauge")


def credentials_metrics(cfg: Config) -> list[str]:
    out: list[str] = []
    path = cfg.credentials_path
    try:
        oauth, ok = read_oauth(path), 1
    except Exception as e:  # noqa: BLE001 - any failure means "unreadable"
        log(f"credentials unreadable: {type(e).__name__}")
        oauth, ok = {}, 0
    gauge(out, "claude_cli_credentials_readable", "1 if the Claude CLI OAuth credentials file parses")
    out.append(f"claude_cli_credentials_readable {ok}")
    for key, name, help_ in (
        (
            "expiresAt",
            "claude_cli_oauth_access_expires_at_seconds",
            "Claude CLI OAuth access token expiry (unix seconds)",
        ),
        (
            "refreshTokenExpiresAt",
            "claude_cli_oauth_refresh_expires_at_seconds",
            "Claude CLI OAuth refresh token expiry (unix seconds); a new login is needed after this",
        ),
    ):
        value = oauth.get(key)
        if is_num(value) and value > 0:
            gauge(out, name, help_)
            out.append(f"{name} {value / 1000:.0f}")
    try:
        mtime = os.stat(path).st_mtime
    except OSError:
        pass
    else:
        gauge(
            out,
            "claude_cli_credentials_mtime_seconds",
            "Last write of the Claude CLI credentials file (refresh or login)",
        )
        out.append(f"claude_cli_credentials_mtime_seconds {mtime:.0f}")
    return out


def usage_metrics(usage: Usage | None) -> list[str]:
    out: list[str] = []
    gauge(out, "claude_usage_up", "1 if the last usage fetch succeeded")
    out.append(f"claude_usage_up {0 if usage is None else 1}")
    usage = usage or Usage()

    gauge(out, "claude_usage_percent", "Claude plan window utilization (0-100)")
    resets = []
    for window, (util, reset) in usage.windows.items():
        out.append(f'claude_usage_percent{{window="{esc(window)}"}} {fmt(util)}')
        if reset:
            resets.append(f'claude_usage_resets_at_seconds{{window="{esc(window)}"}} {reset}')
    gauge(out, "claude_usage_resets_at_seconds", "When the plan window resets (unix seconds)")
    out.extend(resets)

    gauge(out, "claude_usage_limit_percent", "Per-limit usage reported by the plan")
    for lim in usage.limits:
        labels = (
            f'kind="{esc(lim["kind"])}",group="{esc(lim["group"])}",'
            f'scope="{esc(lim["scope"])}",active="{lim["active"]}"'
        )
        out.append(f"claude_usage_limit_percent{{{labels}}} {fmt(lim['percent'])}")

    if usage.extra_utilization is not None:
        gauge(out, "claude_usage_extra_utilization", "Paid overflow (extra usage) utilization")
        out.append(f"claude_usage_extra_utilization {fmt(usage.extra_utilization)}")
    return out


def render(cfg: Config, fetcher=fetch) -> str:
    out = credentials_metrics(cfg)
    try:
        usage: Usage | None = parse_usage(fetcher(cfg))
    except ShapeError as e:
        log(f"unexpected usage response shape: {e}")
        usage = None
    except Exception as e:  # noqa: BLE001 - network, HTTP, JSON: all mean "down"
        log(f"usage fetch failed: {type(e).__name__}")
        usage = None
    out.extend(usage_metrics(usage))
    gauge(out, "claude_usage_exporter_build_info", "Exporter version")
    out.append(f'claude_usage_exporter_build_info{{version="{esc(__version__)}"}} 1')
    return "\n".join(out) + "\n"


class Cache:
    """Serve one render for `cache_seconds`, whatever the scrape rate."""

    def __init__(self, cfg: Config, fetcher=fetch, clock=time.monotonic):
        self.cfg, self.fetcher, self.clock = cfg, fetcher, clock
        self.at: float | None = None
        self.body = ""

    def get(self) -> str:
        now = self.clock()
        if self.at is None or now - self.at >= self.cfg.cache_seconds:
            self.body, self.at = render(self.cfg, self.fetcher), now
        return self.body
