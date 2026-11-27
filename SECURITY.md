# Security

Please report vulnerabilities privately through GitHub's "Report a vulnerability" (Security tab),
not in a public issue.

What the exporter handles: it reads the Claude CLI's OAuth credentials file to send its access token
to Anthropic's usage endpoint. It exports only timestamps from that file and never logs or exports
token values. A way to make it leak a token (in metrics, logs, errors or over the network to anything
but the configured endpoint) is a vulnerability.
