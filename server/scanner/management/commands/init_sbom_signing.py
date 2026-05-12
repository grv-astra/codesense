import json
import subprocess
from pathlib import Path

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Initialize cosign keys and signing config for SBOM signing"

    def handle(self, *args, **options):
        base_dir = Path.cwd()

        keys_dir = base_dir / "keys"
        config_dir = base_dir / "config"

        keys_dir.mkdir(parents=True, exist_ok=True)
        config_dir.mkdir(parents=True, exist_ok=True)

        private_key = keys_dir / "cosign.key"
        public_key = keys_dir / "cosign.pub"
        signing_config = keys_dir / "signing-config.json"

        # --------------------------------------------------
        # Generate cosign key pair
        # --------------------------------------------------
        if not private_key.exists() or not public_key.exists():
            self.stdout.write("Generating cosign key pair...")

            result = subprocess.run(
                [
                    "cosign",
                    "generate-key-pair",
                ],
                cwd=str(keys_dir),
                capture_output=True,
                text=True,
                encoding="utf-8",
            )

            if result.returncode != 0:
                raise Exception(f"Cosign key generation failed: {result.stderr}")

            self.stdout.write(self.style.SUCCESS("Cosign key pair generated"))
        else:
            self.stdout.write("Cosign keys already exist")

        # --------------------------------------------------
        # Generate minimal offline signing config
        # --------------------------------------------------
        if not signing_config.exists():
            self.stdout.write("Creating signing config...")

            config = {
                "mediaType": "application/vnd.dev.sigstore.signingconfig.v0.2+json"
            }

            with open(signing_config, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2)

            self.stdout.write(self.style.SUCCESS("Signing config created"))
        else:
            self.stdout.write("Signing config already exists")

        self.stdout.write(self.style.SUCCESS("SBOM signing initialization complete"))