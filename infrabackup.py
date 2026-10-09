#!/usr/bin/env python3
"""backup.py — Orchestrateur principal infra-backup.

Usage :
    python backup.py            # traite tous les fichiers CONFIG_DIR/*.toml
    python backup.py pc-fixe    # traite uniquement la machine spécifiée
"""

import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import tomllib

from tools import runner
from tools.catalog import run_tools
from tools.files import run_files
from tools.git_watch import run_git_watch
from tools.reports import run_reports
from tools.ssh import check_ssh

SCRIPT_DIR   = Path(__file__).parent
# OUTPUT_DIR   = SCRIPT_DIR / "output"
OUTPUT_DIR   = Path('/home/moi/GIT/backup')
CONFIG_DIR   = OUTPUT_DIR


# ---------------------------------------------------------------------------
# process_machine
# ---------------------------------------------------------------------------
def process_machine(conf_file: Path) -> bool:
    """Charge une config TOML et exécute tous les modules pour cette machine.

    Retourne True en cas de succès, False si la machine est ignorée.
    """
    try:
        with conf_file.open("rb") as f:
            cfg = tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        print(f"[ERROR] {conf_file.name} : fichier TOML invalide — {e}", file=sys.stderr)
        return False

    # Champs obligatoires
    name = cfg.get("name")
    host = cfg.get("host")
    user = cfg.get("user", "")

    if not name or not host:
        print(f"[ERROR] {conf_file} : 'name' et 'host' sont obligatoires", file=sys.stderr)
        return False

    # Pour localhost, on utilise l'utilisateur courant si non précisé
    if host == "localhost" and not user:
        import os
        user = os.environ.get("USER", os.environ.get("USERNAME", ""))

    machine_output = OUTPUT_DIR / name
    runner.mkdir(machine_output)

    print()
    print("═══════════════════════════════════════")
    print(f" Machine : {name} ({host})")
    print("═══════════════════════════════════════")

    # Vérifie la connectivité
    if not check_ssh(host, user):
        print(f"[ERROR] Impossible de joindre {host} — machine ignorée", file=sys.stderr)
        return False

    # Module fichiers
    include = cfg.get("include", [])
    exclude = cfg.get("exclude", [])
    if include:
        # Expansion du ~ pour localhost
        if host == "localhost":
            include = [str(Path(p).expanduser()) for p in include]
            exclude = [str(Path(p).expanduser()) for p in exclude]
        print("[files]")
        run_files(host, user, machine_output, include, exclude=exclude)

    # Module rapports
    reports = cfg.get("reports", [])
    if reports:
        print("[reports]")
        run_reports(host, user, machine_output, reports)

    # Module outils
    tools = cfg.get("tools", [])
    if tools:
        print("[tools]")
        run_tools(host, user, machine_output, tools)

    # Module surveillance Git
    git_repos = cfg.get("git_repos", [])
    if git_repos:
        if host == "localhost":
            git_repos = [str(Path(p).expanduser()) for p in git_repos]
        print("[git-watch]")
        has_issues = run_git_watch(host, user, machine_output, git_repos)
        if has_issues:
            print(f"[WARN] Des repos Git ont des modifications en attente sur {name}", file=sys.stderr)

    return True


# ---------------------------------------------------------------------------
# commit_output
# ---------------------------------------------------------------------------
def commit_output() -> None:
    """Commite tous les changements dans output/ (repo Git)."""
    if not OUTPUT_DIR.exists():
        return

    git_dir = OUTPUT_DIR / ".git"
    if not git_dir.exists():
        print("[WARN] output/ n'est pas un repo Git. Initialiser avec : git init output/", file=sys.stderr)
        return

    runner.run(["git", "add", "-A"], cwd=OUTPUT_DIR, check=True)

    # Vérifie s'il y a des changements stagés (toujours exécuté même en dry-run
    # pour éviter un faux commit sur un repo vide)
    diff = subprocess.run(
        ["git", "diff", "--cached", "--quiet"],
        cwd=OUTPUT_DIR,
    )
    if diff.returncode == 0 and not runner.DRY_RUN:
        print("\n→ Aucun changement détecté, rien à commiter.")
        return

    timestamp = datetime.now(ZoneInfo("Europe/Paris")).strftime("%Y-%m-%d %H:%M")
    runner.run(["git", "commit", "-m", f"backup: {timestamp}"], cwd=OUTPUT_DIR, check=True)
    print(f"→ Commit effectué : backup {timestamp}")

    # Push si un remote est configuré
    remotes = subprocess.run(
        ["git", "remote"],
        check=False,
        cwd=OUTPUT_DIR,
        capture_output=True,
        text=True,
    )
    if remotes.stdout.strip():
        runner.run(["git", "push"], cwd=OUTPUT_DIR, check=True)
        print("→ Push effectué.")


# ---------------------------------------------------------------------------
# Point d'entrée
# ---------------------------------------------------------------------------
def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Orchestrateur infra-backup")
    _ = parser.add_argument(
        "machine",
        nargs="?",
        help="Nom de la machine à traiter (sans .toml). Toutes si omis.",
    )
    _ = parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simule l'exécution : logue toutes les commandes sans les lancer.",
    )
    args = parser.parse_args()

    if args.dry_run:
        log_path = SCRIPT_DIR / f"dry-run-{datetime.now(ZoneInfo("Europe/Paris")).strftime('%Y-%m-%d_%H-%M')}.sh"
        runner.set_dry_run(True, log_path=log_path)
        print(f"[DRY-RUN] Simulation activée — log : {log_path}")

    if args.machine:
        conf_file = CONFIG_DIR / f"{args.machine}.toml"
        if not conf_file.exists():
            print(f"[ERROR] Fichier de config introuvable : {conf_file}", file=sys.stderr)
            sys.exit(1)
        conf_files = [conf_file]
    else:
        conf_files = sorted(CONFIG_DIR.glob("*.toml"))
        if not conf_files:
            print(f"[ERROR] Aucun fichier .toml trouvé dans {CONFIG_DIR}", file=sys.stderr)
            sys.exit(1)

    for conf_file in conf_files:
        _ = process_machine(conf_file)

    # commit_output()


if __name__ == "__main__":
    main()
