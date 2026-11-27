# Terminology

- usage window - a rolling limit period the API reports; each has a utilization and a reset time (metric names: `docs/metrics.md`)
- utilization - percent of a window used: `claude_usage_percent`
- resets_at - when a window resets: `claude_usage_resets_at_seconds` (Unix time)
- credentials file - the CLI's OAuth login file; read only, never written
- up - `claude_usage_up`: 1 when the last upstream call returned a usable response
- schema drift - the undocumented endpoint changing shape; handled by ignoring unknown fields and reporting up 0 on a bad shape
- native package - Debian version with no `-N` revision; the upstream version is the package version
