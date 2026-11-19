import unittest
from pulsegrid.address import address_kind


class AddressTests(unittest.TestCase):
    def test_public_ipv4(self):
        self.assertEqual(address_kind('8.8.8.8'), 'ip')

    def test_domain(self):
        self.assertEqual(address_kind('example.com'), 'dns')

    def test_nonpublic_or_invalid_addresses(self):
        for value in ('127.0.0.1', '192.168.1.1', '::1', '999.999.999.999', '', 'example.com\nBAD=1', '-bad.example'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                address_kind(value)


if __name__ == '__main__':
    unittest.main()
