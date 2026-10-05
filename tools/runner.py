"""tools/runner.py — Wrapper autour de subprocess.run avec mode simulation (dry-run).

Usage :
    from runner import run, set_dry_run

    # Activer la simulation (à appeler une fois au démarrage)
    set_dry_run(True, log_path=Path("dry-run.sh"))

    # Ensuite, tous les appels run(...) sont interceptés et loggés,
    # sans rien exécuter réellement.
    run(["rsync", "-aR", "/etc", "/backup/"])
"""

import shlex
import subprocess
from pathlib import Path

# ---------------------------------------------------------------------------
# État global (modifié uniquement par set_dry_run)
# ---------------------------------------------------------------------------
DRY_RUN: bool = False
_log_path: Path | None = None


def set_dry_run(enabled: bool, log_path: Path | None = None) -> None:
    """Active ou désactive le mode simulation.

    Args:
        enabled:  True pour simuler, False pour exécuter réellement.
        log_path: Fichier où écrire les commandes simulées.
                  Si None, les commandes sont affichées sur stdout uniquement.
    """
    global DRY_RUN, _log_path
    DRY_RUN = enabled
    _log_path = log_path

    if enabled and log_path is not None:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        # En-tête du fichier de log
        log_path.write_text("#!/usr/bin/env bash\n# Dry-run — commandes simulées\n\n", encoding="utf-8")


def mkdir(path: Path) -> None:
    """Crée un répertoire. En dry-run, logue l'opération sans créer."""
    if DRY_RUN:
        _log_fs(f"mkdir -p {path}")
        return
    path.mkdir(parents=True, exist_ok=True)


def write_text(path: Path, content: str) -> None:
    """Écrit un fichier texte. En dry-run, logue l'opération sans écrire."""
    if DRY_RUN:
        lines = content.splitlines()
        preview = lines[0] if lines else ""
        suffix = f" ({len(lines)} lignes)" if len(lines) > 1 else ""
        _log_fs(f"# écriture → {path}  '{preview}'{suffix}")
        return
    path.write_text(content, encoding="utf-8")



# ---------------------------------------------------------------------------
# SSH helpers — centralisent la logique localhost vs distant
# ---------------------------------------------------------------------------
_SSH_OPTS = [
    "-o", "BatchMode=yes",
    "-o", "ConnectTimeout=10",
    "-o", "StrictHostKeyChecking=accept-new",
]


def ssh_target(user: str, host: str) -> str:
    """Retourne 'user@host' si user est défini, sinon 'host' seul (alias ~/.ssh/config)."""
    return f"{user}@{host}" if user else host


def run_cmd(host: str, user: str, cmd: str, **kwargs) -> subprocess.CompletedProcess:
    """Exécute une commande shell localement ou via SSH selon host.

    L'appelant n'a pas à savoir si c'est local ou distant.
    """
    if host == "localhost":
        return run(cmd, shell=True, **kwargs)
    return run(["ssh", *_SSH_OPTS, ssh_target(user, host), cmd], **kwargs)


def run_rsync(
    host: str,
    user: str,
    paths: list[str],
    dest: str,
    excludes: list[str] | None = None,
) -> subprocess.CompletedProcess:
    """Lance rsync localement ou vers un hôte distant selon host.

    Convention sur les chemins :
    - Chemin avec glob (*) → rsync --no-recursive : premier niveau uniquement,
      les sous-dossiers éventuellement matchés ne sont pas parcourus.
    - Chemin sans glob     → rsync récursif complet (comportement par défaut).

    excludes : motifs passés à --exclude (un flag par entrée), appliqués aux
    deux groupes d'appels (plain et glob). Avec -R, la racine du transfert
    rsync est '/' : les motifs doivent donc être des chemins absolus complets
    (ex : '/storage/.config/dockers/qbittorrent/qBittorrent/BT_backup'),
    utilisables tels quels, identiques aux chemins de 'files'.
    """
    exclude_flags = [f"--exclude={e}" for e in (excludes or [])]

    glob_paths  = [p for p in paths if "*" in p]
    plain_paths = [p for p in paths if "*" not in p]

    results: list[subprocess.CompletedProcess] = []
    if plain_paths:
        results.append(_rsync_call(
            ["rsync", "-aR", "--delete", *exclude_flags], host, user, plain_paths, dest
        ))
    if glob_paths:
        results.append(_rsync_call(
            ["rsync", "-aR", "--no-recursive", "--dirs", "--delete", *exclude_flags],
            host, user, glob_paths, dest
        ))

    if not results:
        return subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")

    # Retourne le résultat le plus défavorable (pire code retour, stderr cumulés)
    worst = max(results, key=lambda r: r.returncode)
    merged_stderr = "\n".join(r.stderr for r in results if r.stderr).strip()
    return subprocess.CompletedProcess(
        args=worst.args, returncode=worst.returncode,
        stdout="", stderr=merged_stderr,
    )


def _rsync_call(
    rsync_base: list[str], host: str, user: str, paths: list[str], dest: str
) -> subprocess.CompletedProcess:
    """Construit et exécute une commande rsync avec les flags donnés."""
    # -a  : archive (récursif, permissions, dates, liens symboliques)
    # -R  : chemins relatifs → préserve l'arborescence complète dans dest
    # --delete : supprime localement ce qui n'existe plus à la source
    if host == "localhost":
        return run(rsync_base + paths + [dest], capture_output=True, text=True)
    remote_sources = [f"{ssh_target(user, host)}:{p}" for p in paths]
    ssh_e = "ssh " + " ".join(_SSH_OPTS)
    return run(
        rsync_base + ["-e", ssh_e] + remote_sources + [dest],
        capture_output=True,
        text=True,
    )


def run(
    cmd: list[str] | str,
    *,
    shell: bool = False,
    input: str | None = None,
    capture_output: bool = False,
    text: bool = False,
    cwd: Path | str | None = None,
    check: bool = False,
    **kwargs,
) -> subprocess.CompletedProcess:
    """Remplace subprocess.run. En mode dry-run, logue la commande sans l'exécuter."""

    if DRY_RUN:
        _log_command(cmd, cwd=cwd, stdin_data=input)
        # Retourne un faux résultat neutre
        return subprocess.CompletedProcess(
            args=cmd, returncode=0, stdout="", stderr=""
        )

    return subprocess.run(
        cmd,
        shell=shell,
        input=input,
        capture_output=capture_output,
        text=text,
        cwd=cwd,
        check=check,
        **kwargs,
    )


# ---------------------------------------------------------------------------
# Fonction interne de log
# ---------------------------------------------------------------------------
def _log_command(
    cmd: list[str] | str,
    cwd: Path | str | None,
    stdin_data: str | None,
) -> None:
    """Formate et enregistre la commande dans le fichier de log (et stdout)."""

    # Représentation lisible de la commande
    if isinstance(cmd, list):
        line = shlex.join(cmd)
    else:
        line = cmd

    if cwd:
        line = f"(cd {shlex.quote(str(cwd))} && {line})"

    # Cas spécial : commande qui reçoit un script via stdin (bash -s)
    if stdin_data:
        line += " <<'EOF'\n" + stdin_data.rstrip("\n") + "\nEOF"

    print(f"[DRY-RUN] {line.splitlines()[0]}" + (" ..." if "\n" in line else ""))

    if _log_path is not None:
        with _log_path.open("a", encoding="utf-8") as f:
            f.write(line + "\n\n")


def _log_fs(line: str) -> None:
    """Logue une opération filesystem (mkdir, write_text)."""
    print(f"[DRY-RUN] {line}")

    if _log_path is not None:
        with _log_path.open("a", encoding="utf-8") as f:
            f.write(line + "\n\n")
