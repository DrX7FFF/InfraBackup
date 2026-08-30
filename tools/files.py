"""tools/files.py — Synchronisation de fichiers via rsync."""

import sys
from pathlib import Path

from tools import runner


def run_files(host: str, user: str, output_dir: Path, files: list[str]) -> None:
    """Synchronise chaque chemin listé vers output_dir/files/ via rsync.

    - Fonctionne pour les fichiers individuels et les répertoires.
    - Préserve l'arborescence complète grâce à l'option -R (chemins relatifs).
    - Supporte les globs (ex : *.json) — rsync remonte une erreur si aucun fichier ne correspond.
    """
    files_dir = output_dir / "files"
    runner.mkdir(files_dir)

    print("  [files]")

    result = runner.run_rsync(host, user, files, str(files_dir) + "/")

    # Supprimer les dossiers vides créés par rsync --dirs (bottom-up)
    for d in sorted(files_dir.rglob("*"), reverse=True):
        if d.is_dir() and not any(d.iterdir()):
            d.rmdir()

    if result.returncode != 0:
        print(f"[WARN] rsync a rencontré des erreurs :\n{result.stderr}", file=sys.stderr)
