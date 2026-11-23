"""Package normal app/boot/public-maintenance artifacts; performs no hardware I/O."""
import argparse
import json
from pathlib import Path
try:
    from .normal_boot import prepare
    from .idt.targets import target_ids
except ImportError:
    from normal_boot import prepare
    from idt.targets import target_ids


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--target", choices=target_ids(), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--tls-backend", choices=("software", "tsip"), default="software")
    options = {"rsu": "normal_app.rsu", "bootloader": "bootloader.mot",
               "bootloader-bank1": "bootloader_bank1.mot", "provisioner-mot": "public_signer_provisioner.mot",
               "provisioner-manifest": "public_signer_provisioner_manifest.json",
               "signer-cert": "signer.crt.pem", "signer-public-key": "signer.pub.pem"}
    for option in options:
        parser.add_argument("--"+option, type=Path, required=True)
    args = parser.parse_args(argv)
    manifest = prepare(args.source, args.target, args.output,
                       {name: getattr(args, option.replace("-", "_")) for option, name in options.items()},
                       tls_backend=args.tls_backend)
    print(json.dumps({name: manifest[name] for name in ("profile", "source_sha", "target_id", "tls_backend")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
