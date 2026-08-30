"""tools/ssh.py — Utilitaires SSH : connexion et exécution de commandes distantes."""

import subprocess
from tools import runner

# ssh_target est défini dans runner pour éviter les imports circulaires
ssh_target = runner.ssh_target


def check_ssh(host: str, user: str) -> bool:
    """Vérifie qu'une connexion SSH est possible. Retourne True si ok."""
    if host == "localhost":
        return True
    if runner.DRY_RUN:
        return True
    result = subprocess.run(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5",
         "-o", "StrictHostKeyChecking=accept-new",
         runner.ssh_target(user, host), "true"],
        capture_output=True,
    )
    return result.returncode == 0


def remote_run(host: str, user: str, cmd: str) -> subprocess.CompletedProcess:
    """Exécute une commande sur la machine cible (locale ou distante)."""
    return runner.run_cmd(host, user, cmd, capture_output=True, text=True)
