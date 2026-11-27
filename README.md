# claude-usage-exporter

A small Prometheus exporter for your Claude plan's usage limits: the same numbers as `/usage` in
Claude Code (five-hour and weekly utilization, reset times, per-model weekly limits), plus the health
of the Claude CLI login it reads. Comes with a Grafana dashboard that shows weekly usage against an
even pace and projects where you'll land at reset.

- Python 3.11+, standard library only.
- Shipped as a Debian package (`.deb`, any architecture) and a multi-arch container image.
- Reads the Claude CLI's existing OAuth login. **Only timestamps are exported; the token never leaves
  the file**, and it is never logged.

> The repository is moving from `pipthefox/claude-usage-exporter` to `jfryman/claude-usage-exporter`.
> Until it has, use `pipthefox` in the release and image URLs below (GitHub redirects the old
> URLs afterwards).

## How it works

The exporter reads `~/.claude/.credentials.json` (written by `claude` when you log in) and calls
`GET https://api.anthropic.com/api/oauth/usage` with the header `anthropic-beta: oauth-2025-04-20`,
the endpoint Claude Code's own usage view uses. It caches the answer (5 minutes by default),
whatever the scrape rate, and serves Prometheus metrics on `:9101/metrics`.
The full list is in [docs/metrics.md](docs/metrics.md).

The dashboard does the rest in PromQL:

- Week elapsed: `100 * (time() - (resets_at - 604800)) / 604800`
- Projected at reset: `used / week_elapsed * 100`
- Usage added per hour: `clamp_min(delta(claude_usage_percent{window="seven_day"}[1h]), 0)`

## Install (Debian, Ubuntu)

Download the `.deb` and `SHA256SUMS` from the
[latest release](https://github.com/jfryman/claude-usage-exporter/releases/latest), check them, and
install:

```sh
V=0.1.0
base=https://github.com/jfryman/claude-usage-exporter/releases/download/v$V
curl -fLO "$base/claude-usage-exporter_${V}_all.deb" -fLO "$base/SHA256SUMS"
sha256sum --ignore-missing -c SHA256SUMS
sudo apt install "./claude-usage-exporter_${V}_all.deb"
```

Verifying the signature and build provenance is described in [docs/install.md](docs/install.md#verify).

Nothing starts on install: the exporter reads one user's Claude login, so you enable it for that
user. As the user who runs `claude`:

```sh
systemctl --user daemon-reload
systemctl --user enable --now claude-usage-exporter
sudo loginctl enable-linger "$USER"        # keep it running without a login session
curl -s localhost:9101/metrics | grep claude_usage_percent
```

Or as a system service that runs as that user (with systemd sandboxing):

```sh
sudo systemctl enable --now claude-usage-exporter@alice
```

## Configuration

Flags win over environment variables. The units read `/etc/default/claude-usage-exporter`, then a
per-user file (`~/.config/claude-usage-exporter/env` for the user unit,
`/etc/claude-usage-exporter/<user>.env` for the template).

| Flag | Environment | Default |
|---|---|---|
| `--bind` | `CLAUDE_USAGE_BIND` | `127.0.0.1` |
| `--port` | `CLAUDE_USAGE_PORT` | `9101` |
| `--cache-seconds` | `CLAUDE_USAGE_CACHE` | `300` |
| `--credentials` | `CLAUDE_USAGE_CREDENTIALS` | `$CLAUDE_CONFIG_DIR/.credentials.json`, else `~/.claude/.credentials.json` |
| `--url` | `CLAUDE_USAGE_URL` | the usage endpoint (set it only to test against a mock) |
| `--once` | | print the metrics once and exit |
| `--version` | | |

To let a Prometheus on another host scrape it, set `CLAUDE_USAGE_BIND` to an address it can reach.

## Prometheus and Grafana

```yaml
scrape_configs:
  - job_name: claude-usage
    scrape_interval: 1m
    static_configs:
      - targets: ["<host>:9101"]
```

Import `claude-usage-dashboard.json` (a release asset, and installed at
`/usr/share/claude-usage-exporter/`) into Grafana and pick your Prometheus datasource. Example alert
rules: [examples/alerts.yml](examples/alerts.yml).

## Container image

`ghcr.io/jfryman/claude-usage-exporter` (linux/amd64, linux/arm64). Mount a credentials file that
something keeps fresh; see [docs/install.md](docs/install.md#container-and-kubernetes) for why that
matters.

## Caveats

- The usage endpoint is **undocumented**. It can change or disappear without notice. Fields the
  exporter doesn't know are ignored; an answer it can't read gives `claude_usage_up 0`.
- It uses your personal login token, read-only. Don't run it anywhere you wouldn't put that
  credentials file.
- The CLI refreshes its access token (about every 8 hours) when it runs. The exporter only re-reads
  the file and never refreshes the token itself, so it can't race the CLI or log it out. If `claude`
  doesn't run on the host for a while, the access token expires and `claude_usage_up` goes to 0
  until it does.

## Development

```sh
python3 -m pip install -e '.[test,lint]'
python3 -m pytest -q
ruff check . && ruff format --check .
podman run --rm -v "$PWD":/src:ro -v "$PWD/dist":/out debian:trixie /src/scripts/build-deb.sh
podman run --rm -v "$PWD":/src:ro ubuntu:24.04 /src/scripts/smoke-test.sh /src/dist/claude-usage-exporter_*_all.deb
```

Releases: [docs/releasing.md](docs/releasing.md). Changes: [CHANGELOG.md](CHANGELOG.md).

## License

MIT
