"""tools/reports.py — Catalogue des rapports et exécution distante."""

import sys
from pathlib import Path

from tools import runner
from tools.ssh import ssh_target  # noqa: F401  (ré-exporté pour compatibilité)

# ---------------------------------------------------------------------------
# Catalogue : nom → commande shell exécutée sur la cible
# ---------------------------------------------------------------------------
REPORT_CATALOG: dict[str, str] = {
    # Paquets
    "apt-manual":   "apt-mark showmanual",
    "apt-versions": "dpkg-query -W --showformat='${Package} ${Version}\\n'",
    "flatpak":      "flatpak list --app --columns=name,version",
    "snap":         "snap list",
    # Système
    "services": (   "echo '## Activés au boot (enabled)'; "
                    "systemctl list-unit-files --type=service --state=enabled --no-pager; "
                    "echo; echo '## Actifs (running)'; "
                    "systemctl list-units --type=service --state=running --no-pager"),
    "disques":      "df -h",
    "partitions":   "lsblk",
    "materiel":     "lshw -short",
    "reseau":       "ip addr && ip route",
    "crontab":      "crontab -l",
    # Applications
    "docker":       "docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}'",
    "gnome":        "dconf dump /",
    # CoreELEC / Kodi
    "kodi-addons":  "ls /storage/.kodi/addons/",
}


def run_reports(host: str, user: str, output_dir: Path, reports: list[str]) -> None:
    """Exécute chaque rapport et sauvegarde la sortie dans output_dir/reports/."""
    reports_dir = output_dir / "reports"
    runner.mkdir(reports_dir)

    for name in reports:
        cmd = REPORT_CATALOG.get(name)
        if cmd is None:
            print(f"[WARN] Rapport inconnu : '{name}' — ignoré", file=sys.stderr)
            continue

        print(f"  [report] {name}")

        result = runner.run_cmd(host, user, cmd, capture_output=True, text=True)

        output = result.stdout + (result.stderr if result.returncode != 0 else "")
        runner.write_text(reports_dir / f"{name}.txt", output)
