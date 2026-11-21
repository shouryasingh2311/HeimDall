"""Generate isolated demo identities and a loopback HTTPS certificate."""

import argparse
from datetime import timedelta
import hashlib
from ipaddress import IPv4Address
import json
import os
from pathlib import Path
import secrets

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

from backend.collector.demo_source import DemoSource
from backend.collector.sanitizer import pseudonym
from backend.shared.models import utc_now


def private_write(path: Path, data: bytes, overwrite: bool = False):
    flags = os.O_WRONLY | os.O_CREAT | (os.O_TRUNC if overwrite else os.O_EXCL)
    fd = os.open(path, flags, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(data)


def write_json(path: Path, data: dict, overwrite: bool = False):
    private_write(path, (json.dumps(data, indent=2) + "\n").encode(), overwrite=overwrite)


def issue_certificates(runtime: Path, overwrite: bool = False):
    now = utc_now()
    ca_key = ec.generate_private_key(ec.SECP256R1())
    server_key = ec.generate_private_key(ec.SECP256R1())
    ca_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Heimdal Local Demo CA")])
    server_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")])

    def certificate(subject, issuer, key):
        return (
            x509.CertificateBuilder().subject_name(subject).issuer_name(issuer)
            .public_key(key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(minutes=5)).not_valid_after(now + timedelta(days=7))
        )

    ca = (
        certificate(ca_name, ca_name, ca_key)
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(ca_key.public_key()), critical=False)
        .add_extension(x509.KeyUsage(False, False, False, False, False, True, True, False, False), critical=True)
        .sign(ca_key, hashes.SHA256())
    )
    leaf = (
        certificate(server_name, ca_name, server_key)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()), critical=False)
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(server_key.public_key()), critical=False)
        .add_extension(x509.KeyUsage(True, False, False, False, False, False, False, False, False), critical=True)
        .add_extension(
            x509.SubjectAlternativeName([x509.DNSName("localhost"), x509.IPAddress(IPv4Address("127.0.0.1"))]),
            critical=False,
        )
        .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
        .sign(ca_key, hashes.SHA256())
    )
    private_write(runtime / "ca.pem", ca.public_bytes(serialization.Encoding.PEM), overwrite=overwrite)
    private_write(runtime / "server.pem", leaf.public_bytes(serialization.Encoding.PEM), overwrite=overwrite)
    private_write(runtime / "server.key", server_key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    ), overwrite=overwrite)


def bootstrap(runtime: Path, saas_port=8443, local_base=9001, force: bool = False):
    if not force and ((runtime / "ca.pem").exists() or (runtime / "saas.json").exists()):
        raise FileExistsError(f"Runtime at {runtime} already initialized")
    runtime.mkdir(mode=0o700, parents=True, exist_ok=True)
    issue_certificates(runtime, overwrite=force)
    credentials = []
    dependencies = {}
    for offset, region in enumerate(("us-east-1", "eu-west-1")):
        label = ("alpha", "beta")[offset]
        tenant, collector = f"tenant-{label}", f"collector-{label}-1"
        token, operator, local_token = (secrets.token_urlsafe(32) for _ in range(3))
        key = secrets.token_hex(32)
        sources = [f"{tenant}:{spec.node_id}" for spec in DemoSource.NODE_SPECS]
        demo_memory_source = f"{tenant}:api-01"
        dependencies[tenant] = {
            pseudonym(key, f"{tenant}:{spec.node_id}"): [
                pseudonym(key, f"{tenant}:{dependency}") for dependency in spec.depends_on
            ]
            for spec in DemoSource.NODE_SPECS
        }
        write_json(runtime / f"collector-{label}.json", {
            "tenant_id": tenant, "collector_id": collector, "region": region, "token": token,
            "hmac_key": key, "local_token": local_token, "source_keys": sources,
            "saas_url": f"https://localhost:{saas_port}", "local_port": local_base + offset,
            "demo_memory_source": demo_memory_source,
        }, overwrite=force)
        write_json(runtime / f"operator-{label}.json", {"tenant_id": tenant, "token": operator}, overwrite=force)
        credentials.extend([
            {"role": "collector", "tenant_id": tenant, "region": region, "collector_id": collector,
             "token_sha256": hashlib.sha256(token.encode()).hexdigest(),
             "source_ids": [pseudonym(key, source) for source in sources],
             "demo_source_ids": [pseudonym(key, demo_memory_source)]},
            {"role": "operator", "tenant_id": tenant, "region": region,
             "token_sha256": hashlib.sha256(operator.encode()).hexdigest()},
        ])
    write_json(runtime / "saas.json", {
        "credentials": credentials, "dev_origin": "http://localhost:5173", "dependencies": dependencies,
    }, overwrite=force)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", type=Path, default=Path(".heimdal/dev"))
    parser.add_argument("--saas-port", type=int, default=8443)
    parser.add_argument("--local-port", type=int, default=9001)
    parser.add_argument("--force", "-f", action="store_true", help="Force overwrite existing runtime files")
    args = parser.parse_args()
    try:
        bootstrap(args.runtime, args.saas_port, args.local_port, force=args.force)
    except FileExistsError:
        parser.exit(1, "Runtime already exists. Use the existing settings, or choose a new runtime directory.\n")
    print(f"Created demo certificates and private credentials in {args.runtime}")


if __name__ == "__main__":
    main()
