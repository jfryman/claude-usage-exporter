# ghcr.io/jfryman/claude-usage-exporter: the exporter, stdlib only, as a non-root user.
FROM python:3.13-slim

LABEL org.opencontainers.image.source="https://github.com/jfryman/claude-usage-exporter" \
      org.opencontainers.image.licenses="MIT"

COPY . /src
RUN pip install --no-cache-dir --no-deps --root-user-action=ignore --disable-pip-version-check /src && rm -rf /src

# Mount the Claude CLI credentials file read-only at /credentials/.credentials.json, and keep it
# fresh from a running CLI (the exporter never refreshes the token): see docs/install.md.
ENV CLAUDE_USAGE_BIND=0.0.0.0 \
    CLAUDE_USAGE_CREDENTIALS=/credentials/.credentials.json \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
USER 65532:65532
EXPOSE 9101
ENTRYPOINT ["claude-usage-exporter"]
