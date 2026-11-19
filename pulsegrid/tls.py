"""TLS certificate validation shared by the installer and core supervisor."""
import hashlib
import ipaddress
import ssl
import time
from pathlib import Path


def _dns_match(pattern, host):
    """Match an exact DNS name or a full-label leftmost wildcard only."""
    try:
        pattern = pattern.rstrip('.').encode('idna').decode('ascii').lower()
        host = host.rstrip('.').encode('idna').decode('ascii').lower()
    except UnicodeError:
        return False
    if '*' not in pattern:
        return bool(pattern) and pattern == host
    pattern_labels = pattern.split('.')
    host_labels = host.split('.')
    return (len(pattern_labels) >= 3 and pattern_labels[0] == '*'
            and all('*' not in label for label in pattern_labels[1:])
            and len(pattern_labels) == len(host_labels)
            and bool(host_labels[0]) and pattern_labels[1:] == host_labels[1:])


def verify_certificate_name(cert, host):
    """Check SAN against an IP or DNS host without deprecated ssl.match_hostname.

    IP addresses only match IP SANs. DNS SANs take precedence over common names.
    This validates identity, not issuer trust; TLS clients verify the trust chain.
    """
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        ip = None
    sans = cert.get('subjectAltName', ())
    if ip is not None:
        for kind, value in sans:
            if kind == 'IP Address':
                try:
                    if ipaddress.ip_address(value) == ip:
                        return
                except ValueError:
                    pass
        raise ValueError('Certificate does not contain the requested IP address')

    dns_names = [value for kind, value in sans if kind == 'DNS']
    if dns_names:
        if any(_dns_match(value, host) for value in dns_names):
            return
    else:
        for relative_name in cert.get('subject', ()):
            for key, value in relative_name:
                if key == 'commonName' and _dns_match(value, host):
                    return
    raise ValueError('Certificate does not match the requested hostname')


def validate_certificate(host, cert_path, key_path):
    """Check hostname, expiry and key pairing. Public trust is checked by clients."""
    if not host or not cert_path or not key_path:
        raise ValueError("TLS requires an IP address or domain, certificate chain, and private key")
    cert_path, key_path = Path(cert_path), Path(key_path)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(str(cert_path), str(key_path))
    cert = ssl._ssl._test_decode_cert(str(cert_path))
    verify_certificate_name(cert, host)
    if ssl.cert_time_to_seconds(cert['notAfter']) <= time.time():
        raise ValueError("TLS certificate has expired")
    if ssl.cert_time_to_seconds(cert['notBefore']) > time.time():
        raise ValueError("TLS certificate is not valid yet")
    return hashlib.sha256(cert_path.read_bytes() + b'\0' + key_path.read_bytes()).hexdigest()


def main():
    import sys
    if len(sys.argv) != 4:
        raise SystemExit("Usage: python3 -m pulsegrid.tls IP_OR_DOMAIN FULLCHAIN PRIVATE_KEY")
    try:
        validate_certificate(*sys.argv[1:])
    except (OSError, ValueError, ssl.SSLError) as exc:
        raise SystemExit("TLS validation failed: " + str(exc))
    print("TLS certificate and key validated for " + sys.argv[1])


if __name__ == '__main__':
    main()
