import unittest
from unittest.mock import patch
from pulsegrid.tls import verify_certificate_name


class CertificateNameTests(unittest.TestCase):
    def test_ip_san_must_match_and_cannot_use_common_name(self):
        cert = {'subjectAltName': (('IP Address', '31.56.196.87'), ('DNS', 'example.com')),
                'subject': ((('commonName', '8.8.8.8'),),)}
        verify_certificate_name(cert, '31.56.196.87')
        with self.assertRaises(ValueError):
            verify_certificate_name(cert, '8.8.8.8')
        with self.assertRaises(ValueError):
            verify_certificate_name({'subjectAltName': (('DNS', '31.56.196.87'),)}, '31.56.196.87')

    def test_dns_san_takes_precedence_and_matches_case_insensitively(self):
        cert = {'subjectAltName': (('DNS', 'Example.COM'),),
                'subject': ((('commonName', 'other.example'),),)}
        verify_certificate_name(cert, 'example.com')
        with self.assertRaises(ValueError):
            verify_certificate_name(cert, 'other.example')

    def test_wildcards_are_limited_to_one_label(self):
        cert = {'subjectAltName': (('DNS', '*.example.com'),)}
        verify_certificate_name(cert, 'www.example.com')
        for host in ('example.com', 'a.b.example.com', 'badexample.com'):
            with self.subTest(host=host), self.assertRaises(ValueError):
                verify_certificate_name(cert, host)
        with self.assertRaises(ValueError):
            verify_certificate_name({'subjectAltName': (('DNS', 'w*.example.com'),)}, 'www.example.com')

    def test_common_name_fallback_for_dns_only(self):
        verify_certificate_name({'subject': ((('commonName', 'example.com'),),)}, 'example.com')
        with self.assertRaises(ValueError):
            verify_certificate_name({'subject': ((('commonName', '8.8.8.8'),),)}, '8.8.8.8')

    def test_no_dependency_on_removed_ssl_match_hostname(self):
        import ssl
        with patch.object(ssl, 'match_hostname', side_effect=AttributeError('removed'), create=True):
            verify_certificate_name({'subjectAltName': (('IP Address', '8.8.8.8'),)}, '8.8.8.8')


if __name__ == '__main__':
    unittest.main()
