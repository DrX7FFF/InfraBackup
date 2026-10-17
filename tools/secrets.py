"""tools/secrets.py — Sauvegarde chiffrée des fichiers sensibles (clé 'secrets' du .toml).

Les chemins sont regroupés dans une archive tar, chiffrée avec age pour la
clé publique 'secret_public_key'. Seule la clé privée correspondante permet
de déchiffrer : le résultat peut être poussé sur GitHub.
Destination : output_dir/secrets.tar.age
Restaurer : age -d -i <clé privée> secrets.tar.age | tar -xf - -C <dossier>

age produit un chiffré différent à chaque exécution : l'empreinte du tar en
clair (secrets.sha256) évite de réécrire l'archive si rien n'a changé.
"""

import hashlib
import shlex
import sys
from pathlib import Path

from tools import runner


def run_secrets(host: str, user: str, output_dir: Path, paths: list[str], public_key: str) -> None:
    """Archive et chiffre les chemins sensibles de la machine."""
    print("  [secrets]")

    # tar -C / : chemins relatifs à la racine, comme pour le module files
    rel = " ".join(shlex.quote(p.lstrip("/")) for p in paths)
    result = runner.run_cmd(host, user, f"tar -C / -cf - {rel}", capture_output=True)
    if result.returncode != 0:
        print(f"[WARN] tar a rencontré des erreurs :\n{result.stderr.decode()}", file=sys.stderr)
    if not result.stdout:
        return

    digest = hashlib.sha256(result.stdout).hexdigest()
    digest_file = output_dir / "secrets.sha256"
    if digest_file.exists() and digest_file.read_text().strip() == digest:
        print("    inchangé")
        return

    runner.run(
        ["age", "-r", public_key, "-o", str(output_dir / "secrets.tar.age")],
        input=result.stdout,
        check=True,
    )
    digest_file.write_text(digest + "\n")
