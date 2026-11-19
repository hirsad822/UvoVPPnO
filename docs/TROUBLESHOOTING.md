# PulseGrid — Usage & Troubleshooting

## Everyday Commands
```bash
systemctl status pulsegrid                 # service status
systemctl restart pulsegrid                # restart
journalctl -u pulsegrid -f                 # live logs
sudo bash install.sh --status              # install + health summary
sudo bash install.sh --update              # update code, keep data & token
sudo bash install.sh --uninstall           # remove service (data kept)
sudo bash install.sh --uninstall --purge   # remove everything incl. data
```

## Verify After Install
```bash
bash scripts/verify.sh
# or manually:
curl -s http://127.0.0.1:8080/api/health
curl -s -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8080/api/dashboard
python3 -m unittest discover -s tests -v
```

## Common Issues

| Symptom | Likely cause | Fix |
|---|---|---|
| `401 Unauthorized` | Wrong/missing token | Re-check token from install output or `/etc/pulsegrid/token`; header must be `Authorization: Bearer <token>` |
| Dashboard won't load | Service down / port blocked | `systemctl status pulsegrid`; `ss -tlnp \| grep 8080`; open firewall (see below) |
| Doctor reports unreachable | Node host/port wrong or firewall | Verify host/port in Nodes tab; test with `nc -vz <host> <port>`; check cloud firewall |
| Subscription empty | All nodes filtered out | Lower `min_score`, check expiry/quota in Users, run Doctor to refresh health |
| High latency in Doctor | Network path / far node | Apply **Low Latency** preset; try a nearer node; re-run Doctor |
| Port already in use | Another service on 8080 | Change port: `PULSEGRID_PORT=8443 systemctl restart pulsegrid` (or edit unit) |

## Firewall Hints
```bash
# UFW (Debian/Ubuntu)
sudo ufw allow 8080/tcp comment 'PulseGrid dashboard'
sudo ufw status

# firewalld (RHEL)
sudo firewall-cmd --permanent --add-port=8080/tcp
sudo firewall-cmd --reload
```

## Logs & Data
- Logs: `journalctl -u pulsegrid -n 100`
- Data: `/var/lib/pulsegrid/pulsegrid.db` (SQLite)
- Config/token: `/etc/pulsegrid/` (token file is `0600`)
- Backup: `cp /var/lib/pulsegrid/pulsegrid.db ~/pulsegrid-backup.db`

## Compliance
Ensure all network configurations respect applicable laws and regulations in your jurisdiction.
