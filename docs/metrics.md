# Metrics

| Metric | Labels | Meaning |
|---|---|---|
| `claude_usage_up` | | 1 if the last usage fetch worked and the answer had a shape the exporter reads |
| `claude_usage_percent` | `window` | Utilization 0-100 of each plan window the endpoint reports (`five_hour`, `seven_day`, ...). A new window shows up as a new `window` value |
| `claude_usage_resets_at_seconds` | `window` | When that window resets (unix seconds) |
| `claude_usage_limit_percent` | `kind`, `group`, `scope`, `active` | Per-limit entries (for example `kind="weekly_scoped", scope="<model>"`) |
| `claude_usage_extra_utilization` | | Paid overflow ("extra usage") utilization, when reported |
| `claude_cli_credentials_readable` | | 1 if the credentials file parses and has an OAuth login |
| `claude_cli_oauth_access_expires_at_seconds` | | Access token expiry. The CLI refreshes it when it runs |
| `claude_cli_oauth_refresh_expires_at_seconds` | | Refresh token expiry. Past this, `claude` needs a new login |
| `claude_cli_credentials_mtime_seconds` | | Last write of the credentials file (last refresh or login) |
| `claude_usage_exporter_build_info` | `version` | Always 1 |

The login metrics are exported even when the usage fetch fails, so you can tell "the endpoint
changed" (`claude_usage_up 0`, `claude_cli_credentials_readable 1`, a fresh access token) from
"the login expired".

## Schema drift

The endpoint is undocumented, so the parser is deliberately loose about what it doesn't know and
strict about what it relies on:

- Unknown top-level fields, `null` windows, and unknown keys inside known objects are ignored.
- A top-level object with a numeric `utilization` becomes a `window`.
- A `limits` entry without a numeric `percent` is skipped.
- If the answer isn't a JSON object, if `limits` isn't a list (or holds non-objects), if
  `extra_usage` isn't an object, or if there is neither a window nor a limit, the exporter logs
  `unexpected usage response shape: ...` and reports `claude_usage_up 0` with no usage series.

The test suite covers both cases with an anonymized recorded response
([tests/fixtures/usage.json](../tests/fixtures/usage.json)).
