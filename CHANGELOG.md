# Changelog

All notable changes to claude-usage-exporter. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/). Metric names and labels are the public interface: a
rename or removal is a breaking change.

## [Unreleased]

## [0.1.1] - 2026-11-27

### Changed
- The repository moved to `jfryman/claude-usage-exporter`. The container image is now published at
  `ghcr.io/jfryman/claude-usage-exporter` (the old `pipthefox` image stays available). No code changes.

## [0.1.0] - 2026-11-27

First packaged release of the exporter that was previously shared as a single script.

### Added
- **Debian package** (`claude-usage-exporter_0.1.0_all.deb`, Debian 12+ and Ubuntu 24.04+): the
  command, the module under `/usr/lib/python3/dist-packages`, a per-user systemd unit, a system
  template unit `claude-usage-exporter@<user>.service` with systemd sandboxing, defaults in
  `/etc/default/claude-usage-exporter`, a man page and the Grafana dashboard. Nothing is enabled on
  install.
- **Container image** `ghcr.io/jfryman/claude-usage-exporter` for linux/amd64 and linux/arm64,
  non-root, with SBOM and provenance.
- **Configuration by flag or environment**: `--bind`, `--port`, `--cache-seconds`,
  `--credentials` (defaults to `$CLAUDE_CONFIG_DIR/.credentials.json` when that is set), `--url`
  for testing, `--once` and `--version`.
- **`/healthz`** and **`claude_usage_exporter_build_info{version}`**.
- **Signed releases**: `SHA256SUMS` with a detached signature, a signed tag, and build provenance
  for the `.deb`.

### Changed
- **Tolerant of schema drift**: unknown fields are ignored, and an answer with a shape the exporter
  can't read now reports `claude_usage_up 0` (with a log line) instead of failing the scrape.
- **Concurrent scrapes share one upstream call**; the cache uses a monotonic clock.
- `claude_usage_resets_at_seconds` and `claude_usage_extra_utilization` now have `# HELP` lines.
  Metric names, labels and values are unchanged from the script.

[Unreleased]: https://github.com/jfryman/claude-usage-exporter/compare/v0.1.1...HEAD
[0.1.1]: https://github.com/jfryman/claude-usage-exporter/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/jfryman/claude-usage-exporter/releases/tag/v0.1.0
