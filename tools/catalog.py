"""tools/catalog.py — Catalogue des outils (clé 'tools' du .toml).

Un outil est une fonction fn(host, user, output_dir) -> None.
Pour en ajouter un : écrire la fonction, puis l'enregistrer dans TOOL_CATALOG.
"""

import sys
from pathlib import Path

from tools.user_services import run_user_services

TOOL_CATALOG = {
    "user-services": run_user_services,
}


def run_tools(host: str, user: str, output_dir: Path, tools: list[str]) -> None:
    """Exécute chaque outil demandé."""
    for name in tools:
        fn = TOOL_CATALOG.get(name)
        if fn is None:
            print(f"[WARN] Outil inconnu : '{name}' — ignoré", file=sys.stderr)
            continue
        print(f"  [tool] {name}")
        fn(host, user, output_dir)
