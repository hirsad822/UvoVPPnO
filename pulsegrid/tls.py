"""TLS certificate validation shared by the installer and core supervisor."""
import hashlib
import ssl
import time
from pathlib import Path


def validate_certificate(host, cert_path, key_path):
    """Check hostname, expiry and key pairing. Public trust is checked by clients."""
    if not host or not cert_path or not key_path:
        raise ValueError("TLS requires a domain, certificate chain, and private key")
    cert_path, key_path = Path(cert_path), Path(key_path)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(str(cert_path), str(key_path))
    cert = ssl._ssl._test_decode_cert(str(cert_path))
    ssl.match_hostname(cert, host)
    if ssl.cert_time_to_seconds(cert['notAfter']) <= time.time():
        raise ValueError("TLS certificate has expired")
    if ssl.cert_time_to_seconds(cert['notBefore']) > time.time():
        raise ValueError("TLS certificate is not valid yet")
    return hashlib.sha256(cert_path.read_bytes() + b'\0' + key_path.read_bytes()).hexdigest()


def main():
    import sys
    if len(sys.argv) != 4:
        raise SystemExit("Usage: python3 -m pulsegrid.tls DOMAIN FULLCHAIN PRIVATE_KEY")
    try:
        validate_certificate(*sys.argv[1:])
    except (OSError, ValueError, ssl.SSLError) as exc:
        raise SystemExit("TLS validation failed: " + str(exc))
    print("TLS certificate and key validated for " + sys.argv[1])


if __name__ == '__main__':
    main()
