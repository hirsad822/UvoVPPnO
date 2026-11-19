// tlscheck validates a certificate/key pair and its IP or DNS identity.
// It does not validate public trust; that is the responsibility of TLS clients.
package main

import (
	"crypto/sha256"
	"crypto/tls"
	"crypto/x509"
	"encoding/hex"
	"errors"
	"fmt"
	"os"
	"time"
)

func validate(host, certPath, keyPath string, now time.Time) (string, error) {
	if host == "" {
		return "", errors.New("empty host")
	}
	certPEM, err := os.ReadFile(certPath)
	if err != nil {
		return "", err
	}
	keyPEM, err := os.ReadFile(keyPath)
	if err != nil {
		return "", err
	}
	pair, err := tls.X509KeyPair(certPEM, keyPEM)
	if err != nil {
		return "", fmt.Errorf("certificate/key: %w", err)
	}
	cert, err := x509.ParseCertificate(pair.Certificate[0])
	if err != nil {
		return "", err
	}
	if err = cert.VerifyHostname(host); err != nil {
		return "", err
	}
	if now.Before(cert.NotBefore) || !now.Before(cert.NotAfter) {
		return "", errors.New("certificate is not currently valid")
	}
	h := sha256.New()
	h.Write(certPEM)
	h.Write([]byte{0})
	h.Write(keyPEM)
	return hex.EncodeToString(h.Sum(nil)), nil
}

func main() {
	if len(os.Args) != 4 {
		fmt.Fprintln(os.Stderr, "usage: tlscheck HOST FULLCHAIN PRIVATE_KEY")
		os.Exit(2)
	}
	digest, err := validate(os.Args[1], os.Args[2], os.Args[3], time.Now())
	if err != nil {
		fmt.Fprintln(os.Stderr, "TLS validation failed:", err)
		os.Exit(1)
	}
	fmt.Println(digest)
}
