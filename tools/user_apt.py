"""tools/user_apt.py — Paquets apt installés par l'utilisateur.

apt-mark showmanual moins les paquets fournis par l'OS (reports/apt-os-manifest.txt)
et moins la sélection de l'utilisateur (reports/apt-user-manifest.txt, s'il existe).
Le manifeste de l'ISO (clé 'os_manifest_url' du .toml) ne change pas : il
n'est téléchargé que s'il est absent.
Destination : output_dir/reports/apt-manual-filtered.txt
"""

import sys
import urllib.request
from pathlib import Path

from tools import runner


def run_user_apt(host: str, user: str, output_dir: Path, cfg: dict) -> None:
    """Écrit la liste des paquets manuels absents du manifeste de l'OS."""
    reports_dir = output_dir / "reports"
    manifest = reports_dir / "apt-os-manifest.txt"

    if not manifest.exists():
        print("    téléchargement du manifeste")
        try:
            with urllib.request.urlopen(cfg["os_manifest_url"], timeout=30) as r:
                manifest.write_bytes(r.read())
        except OSError as e:
            print(f"[WARN] Manifeste non téléchargé : {e} — user-apt ignoré", file=sys.stderr)
            return

    known = {line.split()[0].removesuffix(":amd64") for line in manifest.read_text().splitlines() if line.strip()}

    # Sélection maintenue par l'utilisateur (un paquet par ligne)
    user_manifest = reports_dir / "apt-user-manifest.txt"
    if user_manifest.exists():
        known |= {line.split()[0] for line in user_manifest.read_text().splitlines() if line.strip()}

    result = runner.run_cmd(host, user, "apt-mark showmanual", capture_output=True, text=True)
    if result.stderr:
        print(f"[WARN] apt-mark a rencontré des erreurs :\n{result.stderr}", file=sys.stderr)
    pkgs = [p for p in result.stdout.splitlines() if p not in known]

    runner.write_text(reports_dir / "apt-manual-filtered.txt", "".join(f"{p}\n" for p in pkgs))
