#!/usr/bin/env python3
"""Fetch the public code-signing certificate used by an AWS Signer profile."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def run_json(command: list[str]) -> dict:
    print("+ " + " ".join(command))
    result = subprocess.run(command, capture_output=True, text=True)
    if result.stderr:
        print(result.stderr.rstrip(), file=sys.stderr)
    if result.returncode != 0:
        raise RuntimeError(f"command failed with exit {result.returncode}: {' '.join(command)}")
    return json.loads(result.stdout)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--signing-profile", required=True)
    parser.add_argument("--region", required=True)
    parser.add_argument("--out", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    profile = run_json(
        [
            "aws",
            "signer",
            "get-signing-profile",
            "--profile-name",
            args.signing_profile,
            "--region",
            args.region,
            "--output",
            "json",
        ]
    )
    certificate_arn = profile.get("signingMaterial", {}).get("certificateArn")
    if not certificate_arn:
        raise RuntimeError(f"signing profile has no ACM certificateArn: {args.signing_profile}")

    certificate = run_json(
        [
            "aws",
            "acm",
            "get-certificate",
            "--certificate-arn",
            certificate_arn,
            "--region",
            args.region,
            "--output",
            "json",
        ]
    ).get("Certificate")
    if not certificate:
        raise RuntimeError(f"ACM did not return a certificate for {certificate_arn}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(certificate.rstrip() + "\n", encoding="ascii")
    print(f"Fetched AWS Signer certificate: {args.out}")
    print(f"  signing_profile: {args.signing_profile}")
    print(f"  certificate_arn: {certificate_arn}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
