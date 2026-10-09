"""tools/user_services.py — Sauvegarde des services systemd créés à la main.

Copie les fichiers .service (et les drop-ins *.service.d/*.conf) de
/etc/systemd/system qui n'appartiennent à aucun paquet (dpkg -S).
Les liens symboliques (activations *.wants/) sont ignorés.
Destination : output_dir/files/ (même arborescence que le module files :
restaurer = recopier files/etc/... vers /).
"""

import sys
from pathlib import Path

from tools import runner

SYSTEMD_DIR = "/etc/systemd/system"

# Liste les fichiers réguliers, puis écarte ceux dont un paquet est propriétaire.
_FIND_CMD = (
    f"find {SYSTEMD_DIR} -type f \\( -name '*.service' -o -path '*.service.d/*.conf' \\) "
    "| while read -r f; do dpkg -S \"$f\" >/dev/null 2>&1 || echo \"$f\"; done"
)


def run_user_services(host: str, user: str, output_dir: Path) -> None:
    """Sauvegarde les unités systemd système créées manuellement."""
    result = runner.run_cmd(host, user, _FIND_CMD, capture_output=True, text=True)
    paths = sorted(p for p in result.stdout.splitlines() if p.strip())

    if not paths:
        print("    aucune unité manuelle trouvée")
        return

    # for p in paths:
    #     print(f"    {p}")

    dest = output_dir / "files"
    runner.mkdir(dest)

    # Supprime les copies d'unités qui n'existent plus (ou qui sont devenues
    # propriété d'un paquet). Ne touche qu'aux .service / *.service.d/*.conf
    # de /etc/systemd/system, pas au reste de files/.
    if not runner.DRY_RUN:
        wanted = set(paths)
        local_dir = dest / SYSTEMD_DIR.lstrip("/")
        if local_dir.exists():
            for f in sorted(local_dir.rglob("*"), reverse=True):
                if f.is_file() and f.suffix in (".service", ".conf") and "/" + str(f.relative_to(dest)) not in wanted:
                    f.unlink()
                elif f.is_dir() and not any(f.iterdir()):
                    f.rmdir()

    rsync = runner.run_rsync(host, user, paths, str(dest) + "/")
    if rsync.returncode != 0:
        print(f"[WARN] rsync a rencontré des erreurs :\n{rsync.stderr}", file=sys.stderr)
