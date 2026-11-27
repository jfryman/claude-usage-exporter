#!/bin/sh
# Install the .deb in a clean Debian/Ubuntu container and scrape it against a mock usage endpoint
# with a fake login. Run from the repo root:
#   podman run --rm -v "$PWD":/src:ro ubuntu:24.04 /src/scripts/smoke-test.sh /src/dist/claude-usage-exporter_*_all.deb
set -eu
DEB=$1
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
cp "$DEB" /tmp/
apt-get install -y -qq --no-install-recommends /tmp/"$(basename "$DEB")" curl >/dev/null
claude-usage-exporter --version

# Nothing auto-enabled, files in place
test -f /usr/lib/systemd/user/claude-usage-exporter.service
test -f /usr/lib/systemd/system/claude-usage-exporter@.service
test -f /etc/default/claude-usage-exporter
test -f /usr/share/claude-usage-exporter/claude-usage-dashboard.json
test ! -e /etc/systemd/user/default.target.wants/claude-usage-exporter.service
test ! -e /etc/systemd/system/multi-user.target.wants/claude-usage-exporter@.service
python3 -c 'import claude_usage_exporter, sys; print(claude_usage_exporter.__file__)' | grep -q '^/usr/lib/python3/dist-packages/'

# A user with a fake Claude login, a mock endpoint, the packaged binary
useradd -m alice
install -d -o alice -m 0700 /home/alice/.claude
install -o alice -m 0600 /src/tests/fixtures/credentials.json /home/alice/.claude/.credentials.json
python3 /src/scripts/mock-upstream.py --port 18080 /src/tests/fixtures/usage.json &
mock=$!
# Same environment the units load: /etc/default, then the per-user file.
install -d -o alice /home/alice/.config/claude-usage-exporter
echo 'CLAUDE_USAGE_URL=http://127.0.0.1:18080/api/oauth/usage' > /home/alice/.config/claude-usage-exporter/env
su alice -s /bin/sh -c 'set -a; . /etc/default/claude-usage-exporter; . ~/.config/claude-usage-exporter/env; exec claude-usage-exporter' &
for i in $(seq 1 50); do curl -fs http://127.0.0.1:9101/healthz >/dev/null 2>&1 && break; sleep 0.2; done
curl -fsS http://127.0.0.1:9101/metrics | tee /tmp/metrics.txt
grep -qx 'claude_usage_up 1' /tmp/metrics.txt
grep -qx 'claude_usage_percent{window="seven_day"} 42.0' /tmp/metrics.txt
grep -qx 'claude_cli_credentials_readable 1' /tmp/metrics.txt
grep -q 'FAKE-TEST-TOKEN' /tmp/metrics.txt && { echo "token leaked" >&2; exit 1; }
kill "$mock"
# upstream gone: still serves, reports down (cache 0 so it refetches)
su alice -s /bin/sh -c 'CLAUDE_USAGE_URL=http://127.0.0.1:18080/x claude-usage-exporter --once' | grep -qx 'claude_usage_up 0'

apt-get remove -y -qq claude-usage-exporter >/dev/null
test -f /etc/default/claude-usage-exporter   # conffile kept until purge
apt-get purge -y -qq claude-usage-exporter >/dev/null
test ! -e /etc/default/claude-usage-exporter
echo "smoke test: OK on $(. /etc/os-release; echo "$PRETTY_NAME")"
