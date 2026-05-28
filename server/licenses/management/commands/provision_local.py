import json
import os

import requests
from django.conf import settings
from django.core.management.base import BaseCommand
from dotenv import load_dotenv

from licenses.services import crypto, utils
from local.auth_app.utils.account_integrity import sync_protected_accounts


class Command(BaseCommand):
    help = "Provision this local server with Central license server."
    requires_system_checks = []

    def add_arguments(self, parser):
        parser.add_argument("--config", default="central_config.json", help="Path to license config.json")
        parser.add_argument("--outdir", default="./license_data", help="Directory to save keys/config")
        parser.add_argument("--central-url", default=None, help="Override Central server base URL")

    def handle(self, *args, **options):
        config_path = options["config"]
        outdir = options["outdir"]
        override_central_url = options["central_url"]

        if not os.path.exists(config_path):
            self.stderr.write(f"ERROR: config.json not found at {config_path}")
            return

        with open(config_path) as f:
            base_config = json.load(f)

        license_id = base_config["license_id"]

        load_dotenv()
        central_url = (
            override_central_url
            or base_config.get("central_url")
            or getattr(settings, "CENTRAL_URL", None)
            or "http://localhost:8000"
        )
        if not central_url:
            self.stderr.write("ERROR: CENTRAL_URL not set in .env")
            return
        central_url = central_url.rstrip("/")
        self.stdout.write(self.style.NOTICE(f"Central URL: {central_url}"))

        host_id = utils.generate_host_id()
        self.stdout.write(self.style.NOTICE(f"Host ID: {host_id}"))

        os.makedirs(outdir, exist_ok=True)

        local_private, local_public = crypto.generate_keypair()
        priv_path = os.path.join(outdir, "local_private.pem")
        pub_path = os.path.join(outdir, "local_public.pem")

        crypto.save_private_key(local_private, priv_path)
        crypto.save_public_key(local_public, pub_path)

        self.stdout.write(self.style.SUCCESS(f"Local keypair saved at {outdir}"))

        with open(pub_path) as f:
            local_pub_pem = f.read()

        try:
            resp = requests.post(
                f"{central_url}/api/local/provision/",
                json={
                    "license_id": license_id,
                    "local_pubkey": local_pub_pem,
                    "machine_uuid": host_id,
                },
                timeout=15,
            )
        except requests.RequestException as exc:
            self.stderr.write(f"ERROR: Could not reach Central at {central_url}: {exc}")
            return

        if resp.status_code != 201:
            mismatch_hint = ""
            if resp.status_code == 404 and "Invalid or inactive license" in resp.text:
                mismatch_hint = (
                    " Hint: this usually means the license_id exists in a different Central database "
                    "or you are pointing at the wrong CENTRAL_URL."
                )
            self.stderr.write(f"ERROR: Provision failed: {resp.status_code} {resp.text}")
            if mismatch_hint:
                self.stderr.write(mismatch_hint)
            return

        data = resp.json()

        final_config = {
            **base_config,
            "central_url": central_url,
            "local_id": data["local_id"],
            "machine_uuid": host_id,
            "provisioning_jwt": data["provisioning_jwt"],
            "local_private_key_path": priv_path,
            "local_public_key_path": pub_path,
        }
        final_config["central_pubkey"] = base_config.get("central_pubkey")

        cfg_path = os.path.join(outdir, "license_config.json")
        with open(cfg_path, "w") as f:
            json.dump(final_config, f, indent=2)

        sync_protected_accounts(created_by="provisioning")
        self.stdout.write(self.style.SUCCESS(f"Provisioned successfully. Config saved to {cfg_path}"))
