"""Validate public addresses used for certificate issuance."""
import ipaddress
import re


def address_kind(host):
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        # Numeric dotted inputs that aren't valid IPs must not become DNS names.
        if not host or len(host) > 253 or re.fullmatch(r'[0-9.]+', host):
            raise ValueError('Enter a public IPv4 address or DNS name')
        labels = host.split('.')
        if len(labels) < 2 or any(not re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?', label) for label in labels):
            raise ValueError('Invalid DNS name')
        return 'dns'
    if ip.version != 4 or not ip.is_global:
        raise ValueError('A public IPv4 address is required for IP certificates')
    return 'ip'


def main():
    import sys
    if len(sys.argv) != 2:
        raise SystemExit('Usage: python3 -m pulsegrid.address PUBLIC_IP_OR_DOMAIN')
    try:
        print(address_kind(sys.argv[1]))
    except ValueError as exc:
        raise SystemExit(str(exc))


if __name__ == '__main__':
    main()
