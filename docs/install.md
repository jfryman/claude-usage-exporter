# Installing and running

## Debian package

The `.deb` is `Architecture: all` and depends only on `python3 (>= 3.11)`: Debian 12+ and Ubuntu
24.04+ work. It installs:

| Path | What |
|---|---|
| `/usr/bin/claude-usage-exporter` | the command |
| `/usr/lib/python3/dist-packages/claude_usage_exporter/` | the module |
| `/usr/lib/systemd/user/claude-usage-exporter.service` | per-user unit |
| `/usr/lib/systemd/system/claude-usage-exporter@.service` | system template, runs as `User=%i` |
| `/etc/default/claude-usage-exporter` | defaults for both units (conffile, all commented out) |
| `/usr/share/claude-usage-exporter/claude-usage-dashboard.json` | Grafana dashboard |
| `man claude-usage-exporter` | manual |

No unit is enabled or started by the package, for any user. Upgrades don't restart running
exporters either: restart them yourself (`systemctl --user restart claude-usage-exporter`, or
`sudo systemctl restart 'claude-usage-exporter@*'`). Removing the package keeps
`/etc/default/claude-usage-exporter`; purging removes it.

### Which unit

- **User unit** (`systemctl --user enable --now claude-usage-exporter`): simplest, runs in the
  user's own service manager. Needs `loginctl enable-linger <user>` so it runs without a session.
  Overrides go in `~/.config/claude-usage-exporter/env`.
- **Template** (`systemctl enable --now claude-usage-exporter@<user>`): a system service running as
  that user, with systemd sandboxing (read-only home and system, no privileges). Overrides go in
  `/etc/claude-usage-exporter/<user>.env`.

Use one or the other for a given user. Two exporters on one port fail to start.

### Config management

The package is a plain file with a checksum, so configuration management can pin both. Puppet:

```puppet
$version = '0.1.0'
$deb     = "/var/cache/claude-usage-exporter/claude-usage-exporter_${version}_all.deb"
file { '/var/cache/claude-usage-exporter': ensure => directory }
file { $deb:
  source         => "https://github.com/jfryman/claude-usage-exporter/releases/download/v${version}/claude-usage-exporter_${version}_all.deb",
  checksum       => 'sha256',
  checksum_value => '<sha256 from SHA256SUMS>',
}
package { 'claude-usage-exporter':
  ensure   => $version,
  provider => 'apt',
  source   => $deb,
  require  => File[$deb],
}
```

Then manage the user's `~/.config/claude-usage-exporter/env` and enable the unit for that user
(`loginctl enable-linger`, then `systemctl --user -M <user>@ enable --now claude-usage-exporter`).

## Verify

Every release has `SHA256SUMS`, a detached signature `SHA256SUMS.asc` by the release key, and GitHub
build provenance for the `.deb`:

```sh
sha256sum --ignore-missing -c SHA256SUMS
gpg --verify SHA256SUMS.asc SHA256SUMS
gh attestation verify claude-usage-exporter_0.1.0_all.deb --repo jfryman/claude-usage-exporter
```

Import the release key from its GitHub account first (`curl -s https://github.com/pipthefox.gpg |
gpg --import`) and check the fingerprint: `79C5 A318 06F1 AAE4 2107  BD44 187A 16A9 2C56 75DF`.
The release tags are signed with the same key (`git tag -v v0.1.0`).

## From source

```sh
pip install 'git+https://github.com/jfryman/claude-usage-exporter@v0.1.0'
```

## Container and Kubernetes

`ghcr.io/jfryman/claude-usage-exporter:<version>` (linux/amd64 + linux/arm64, with SBOM and
provenance). It runs as uid 65532, listens on `0.0.0.0:9101` and reads
`/credentials/.credentials.json`:

```sh
docker run --rm -p 9101:9101 --user "$(id -u):$(id -g)" \
  -v "$HOME/.claude/.credentials.json:/credentials/.credentials.json:ro" \
  ghcr.io/jfryman/claude-usage-exporter:0.1.0
```

The catch: the exporter never refreshes the OAuth token, and the access token lasts about 8 hours.
The mounted file has to be kept fresh by a Claude CLI that actually runs, for example a hostPath to
the home of a node where `claude` is used, or a volume the CLI writes to. A copied snapshot of the
file works until its access token expires, then `claude_usage_up` drops to 0. Mount it read-only:
the exporter never writes it. The file is normally mode 0600, so run the container as the file's
owner (`--user`, or `runAsUser`/`fsGroup` in Kubernetes).

A minimal Deployment:

```yaml
containers:
  - name: claude-usage-exporter
    image: ghcr.io/jfryman/claude-usage-exporter:0.1.0
    ports: [{name: metrics, containerPort: 9101}]
    readinessProbe: {httpGet: {path: /healthz, port: metrics}}
    securityContext:
      readOnlyRootFilesystem: true
      allowPrivilegeEscalation: false
      capabilities: {drop: [ALL]}
    volumeMounts:
      - {name: credentials, mountPath: /credentials, readOnly: true}
```
