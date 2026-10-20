"""tools/secrets.py — Sauvegarde chiffrée des fichiers sensibles (clé 'secrets' du .toml).

Les chemins sont regroupés dans une archive tar, chiffrée avec age pour la
clé publique 'secret_public_key'. Seule la clé privée correspondante permet
de déchiffrer : le résultat peut être poussé sur GitHub.
Destination : output_dir/secrets.tar.age
Restaurer : age -d -i <clé privée> secrets.tar.age | tar -xf - -C <dossier>

secrets.sha256 (en clair) : une empreinte par fichier. Un secret absent ou
modifié apparaît dans la diff ; s'il est inchangé, l'archive n'est pas réécrite
(age produit un chiffré différent à chaque exécution).
"""

import shlex
import sys
from pathlib import Path

from tools import runner


def run_secrets(host: str, user: str, output_dir: Path, paths: list[str], public_key: str) -> None:
    """Archive et chiffre les chemins sensibles de la machine."""
    print("  [secrets]")

    # Chemins relatifs à la racine, comme pour le module files
    rel = " ".join(shlex.quote(p.lstrip("/")) for p in paths)

    sums = runner.run_cmd(host, user, f"cd / && find {rel} -type f -exec sha256sum {{}} +",
                          capture_output=True, text=True)
    if sums.returncode != 0:
        print(f"[WARN] secrets absents ou illisibles :\n{sums.stderr}", file=sys.stderr)
    manifest = "".join(sorted(sums.stdout.splitlines(keepends=True), key=lambda l: l.split(None, 1)[-1]))
    if not manifest:
        return

    digest_file = output_dir / "secrets.sha256"
    if digest_file.exists() and digest_file.read_text() == manifest:
        print("    inchangé")
        return

    result = runner.run_cmd(host, user, f"tar -C / -cf - {rel}", capture_output=True)
    if result.returncode != 0:
        print(f"[WARN] tar a rencontré des erreurs :\n{result.stderr.decode()}", file=sys.stderr)
    if not result.stdout:
        return

    runner.run(
        ["age", "-r", public_key, "-o", str(output_dir / "secrets.tar.age")],
        input=result.stdout,
        check=True,
    )
    digest_file.write_text(manifest)
