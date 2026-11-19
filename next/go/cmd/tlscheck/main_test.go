package main

import (
	"crypto/rand"
	"crypto/rsa"
	"crypto/x509"
	"crypto/x509/pkix"
	"encoding/pem"
	"math/big"
	"net"
	"os"
	"path/filepath"
	"testing"
	"time"
)

func TestValidate(t *testing.T) {
	now := time.Now()
	key, err := rsa.GenerateKey(rand.Reader, 2048)
	if err != nil {
		t.Fatal(err)
	}
	template := &x509.Certificate{SerialNumber: big.NewInt(1), Subject: pkix.Name{CommonName: "unused"}, DNSNames: []string{"example.com"}, IPAddresses: []net.IP{net.ParseIP("8.8.8.8")}, NotBefore: now.Add(-time.Hour), NotAfter: now.Add(time.Hour), KeyUsage: x509.KeyUsageDigitalSignature}
	der, err := x509.CreateCertificate(rand.Reader, template, template, &key.PublicKey, key)
	if err != nil {
		t.Fatal(err)
	}
	dir := t.TempDir()
	cert, secret := filepath.Join(dir, "cert.pem"), filepath.Join(dir, "key.pem")
	if err := os.WriteFile(cert, pem.EncodeToMemory(&pem.Block{Type: "CERTIFICATE", Bytes: der}), 0600); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(secret, pem.EncodeToMemory(&pem.Block{Type: "RSA PRIVATE KEY", Bytes: x509.MarshalPKCS1PrivateKey(key)}), 0600); err != nil {
		t.Fatal(err)
	}
	for _, host := range []string{"example.com", "8.8.8.8"} {
		if digest, err := validate(host, cert, secret, now); err != nil || len(digest) != 64 {
			t.Fatalf("%s %s %v", host, digest, err)
		}
	}
	for _, host := range []string{"other.example", "8.8.4.4"} {
		if _, err := validate(host, cert, secret, now); err == nil {
			t.Fatalf("accepted %s", host)
		}
	}
	if _, err := validate("example.com", cert, secret, now.Add(2*time.Hour)); err == nil {
		t.Fatal("accepted expired certificate")
	}
}
