# PulseGrid

A lightweight dashboard for managing VLESS nodes and users. It includes a
connection doctor, health-filtered subscription links, advisory presets, and a
managed Xray core. The Python dashboard has no third-party Python dependencies;
the installer downloads a pinned Xray release and verifies its SHA-256 hash.

## Requirements

- Linux with systemd, Python 3.10+, root access, curl and unzip; x86_64 or arm64.
- A public IPv4 address, or a domain whose DNS points to the server. Ports **80/TCP** (certificate
  issuance/renewal), **8080/TCP** (dashboard), and **10000/TCP** (core) must be
  reachable; restrict dashboard access to trusted IPs where possible.
- Port 80 must be free while Certbot uses the standalone challenge. The public IP or domain
  must be publicly reachable for Let's Encrypt to issue a certificate.
- The server needs access to GitHub releases, PyPI and Let's Encrypt.

## Installation and updates

After these changes are merged to `main`, download the installer and provide your
public IPv4 address (do not include `https://`):

```bash
curl -fsSL https://raw.githubusercontent.com/hirsad822/UvoVPPnO/main/install.sh -o install.sh
sudo env PULSEGRID_PUBLIC_HOST=YOUR_PUBLIC_IPV4 bash install.sh
```

For an existing installation use the same command with `--update` after
`install.sh`. To test a branch before merging, download that branch's installer
and set `PULSEGRID_REF` to the same branch name. The installer installs a dedicated Certbot virtual environment, requests a certificate using its standalone HTTP challenge,
installs Xray and enables the service. An already issued certificate in
`/etc/letsencrypt/live/<IP-or-domain>/` is reused. Alternatively supply your own
certificate and private key using `PULSEGRID_TLS_CERT` and `PULSEGRID_TLS_KEY`.

The installer prints the dashboard URL, token and service commands. Open
`https://YOUR_PUBLIC_IPV4:8080`, enter the token, add a user, wait a few seconds,
then click **Check all health** and copy the subscription. Both the dashboard
and managed Xray core use TLS. Subscription URLs contain credentials; keep them
private and share them only with the intended user. Old subscription URLs using
short user IDs are no longer accepted; copy new links after upgrading.

```bash
sudo cat /etc/pulsegrid/token
sudo systemctl status pulsegrid
sudo journalctl -u pulsegrid -n 100 --no-pager
sudo bash /opt/pulsegrid/install.sh --status
sudo bash /opt/pulsegrid/install.sh --uninstall          # preserve data
sudo bash /opt/pulsegrid/install.sh --uninstall --purge  # delete data and config
```

`PULSEGRID_PORT` changes the dashboard port; `PULSEGRID_CORE_PORT` changes the
core port. Both default to unprivileged ports 8080 and 10000 respectively. Set
these environment variables when installing/updating, and open the corresponding
ports in your firewall. If an update fails, the old service may still be running.
The installer reports failure if it cannot verify both the dashboard HTTPS and
core TLS handshakes.

### Certificate renewal

For Certbot-managed certificates, a deploy hook copies each renewed certificate
and key into PulseGrid's restricted configuration directory and restarts the
service. IP certificates have a roughly six-day lifetime: automatic renewal is
critical. The installer enables `pulsegrid-certbot-renew.timer` to check twice
daily. Check it with `systemctl status pulsegrid-certbot-renew.timer` and test
with `sudo /opt/pulsegrid-certbot/bin/certbot renew --dry-run`. Port 80 must
remain available for the challenge.
Renewal can fail if another web server occupies port 80. Certbot dry-runs do not
necessarily execute deploy hooks; test the hook according to your Certbot version.
For custom certificates, after renewal run:

```bash
sudo /opt/pulsegrid/scripts/deploy-cert.sh example.com /path/fullchain.pem /path/privkey.pem --restart
```

PulseGrid checks that the certificate matches the IP or domain, is valid by date and
matches the private key. The IP must be directly reachable from the public internet;
private or shared addresses cannot obtain a public certificate. IPv6 is not yet
supported by this installer. Clients and the Doctor additionally verify trust in the
issuing CA. A self-signed certificate will not pass normal client verification.

## Development and verification

```bash
python3 -m unittest discover -s tests -v
PULSEGRID_DATA_DIR=/tmp/pulsegrid-data PULSEGRID_CONFIG_DIR=/tmp/pulsegrid-config \
  python3 -m pulsegrid --host 127.0.0.1 --port 8080 --token dev-token
bash scripts/verify.sh http://127.0.0.1:8080 dev-token
# After production install:
bash /opt/pulsegrid/scripts/verify.sh https://YOUR_PUBLIC_IPV4:8080 "$(sudo cat /etc/pulsegrid/token)"
```

Local development defaults to HTTP and does not launch Xray without its binary,
public IP or domain and certificates. Production TLS is enabled by the generated systemd
configuration. The Doctor verifies certificates; unchecked or failed TLS nodes
are not included in subscriptions. Install/update/status operations require root.

## Important limitations

- The managed core is VLESS over TCP with TLS. The preset selection is advisory;
  it does **not** reconfigure the core. External nodes require their own setup.
- Traffic measurement and quota enforcement are **not integrated with Xray**.
  Do not use the quota display for billing or as an access-control guarantee.
- User changes and expiry are synchronized approximately every five seconds;
  existing connections may remain open. Do not rely on immediate revocation.
- The health score reflects the latest check, not continuous monitoring. Run
  **Check all health** before copying a new subscription.
- Use only in accordance with applicable laws and regulations.

See [architecture](docs/ARCHITECTURE.md), [product](docs/PRODUCT.md), and
[troubleshooting](docs/TROUBLESHOOTING.md). MIT license.
