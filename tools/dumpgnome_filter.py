"""tools/dumpgnome_filter.py — Dump GNOME (dconf) sans les sections exclues.

Lit reports/dumpgnome-exclude.txt (un chemin de section par ligne, maintenu par
l'utilisateur) : un chemin exclut la section et ses sous-sections.
Les nouvelles sections apparaissent donc tant qu'elles ne sont pas exclues.
Destination : output_dir/reports/dumpgnome-filtered.txt
"""

from pathlib import Path

from tools import runner


def run_dumpgnome_filter(host: str, user: str, output_dir: Path, cfg: dict) -> None:
    """Écrit le dump dconf sans les sections listées dans dumpgnome-exclude.txt."""
    reports_dir = output_dir / "reports"
    exclude_file = reports_dir / "dumpgnome-exclude.txt"
    excludes = [l.strip() for l in exclude_file.read_text().splitlines() if l.strip()] if exclude_file.exists() else []

    result = runner.run_cmd(host, user, "dconf dump /", capture_output=True, text=True)

    # Le dump est une suite de blocs « [chemin] + clés » séparés par une ligne vide
    kept = []
    for block in result.stdout.split("\n\n"):
        section = block.split("\n", 1)[0].strip("[]")
        if block.strip() and not any(section == e or section.startswith(e + "/") for e in excludes):
            kept.append(block)

    runner.write_text(reports_dir / "dumpgnome-filtered.txt", "\n\n".join(kept) + "\n")
