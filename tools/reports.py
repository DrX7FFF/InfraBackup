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
    "flatpak":      "flatpak list --app --columns=application,name,version",
    "snap":         "snap list",
    # Système
    "services": (   "echo '## Activés au boot (enabled)'; "
                    "systemctl list-unit-files --type=service --state=enabled --no-pager; "
                    "echo; echo '## Actifs (running)'; "
                    "systemctl list-units --type=service --state=running --no-pager"),
    "disques":      "df -h",
    "partitions":   "lsblk",
    "materiel":     "lshw -short",
    "ip":           "ip addr && ip route",
    "network":      ("nmcli -t -f NAME connection show | while read -r c; do echo \"## $c\"; "
                    "nmcli -f connection.type,ipv4.method,ipv4.addresses,ipv4.gateway,ipv4.dns,ipv6.method "
                    "connection show \"$c\"; echo; done"),
    "crontab":      "crontab -l",
    "firmware":     "LC_ALL=C fwupdmgr get-updates --no-unreported-check --no-metadata-check 2>&1 | grep -v '…: *[0-9]*%'",
    "users":        ("getent passwd | awk -F: '$3>=1000 && $3<65534 {print $1}' | while read -r u; do "
                    "echo \"$(getent passwd \"$u\" | cut -d: -f1,3,4,6,7) : $(id -nG \"$u\")\"; done"),
    # Applications
    "docker":       "docker ps --format 'table {{.Names}}\t{{.Image}}'",
    "dumpgnome":    "dconf dump /",
    "gnome-extensions": "gnome-extensions list --details",
    "codium-extensions": "codium --list-extensions",
    "brave-flags":  "jq -r '.browser.enabled_labs_experiments[]?' ~/.config/BraveSoftware/Brave-Browser/'Local State'",
    "local-bin":    "ls -1 /usr/local/bin",
    "user-bin":     "ls -1 ~/.local/bin",
    "user-app":     "ls -1 ~/App",
    "user-launchers": "ls -1 ~/.local/share/applications | grep '\\.desktop$'",
    # CoreELEC / Kodi
    "kodi-addons":  "ls /storage/.kodi/addons/",
    "jackett-indexers": "cd /storage/.config/dockers/jackett/Jackett/Indexers && ls -1 *.json",
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
