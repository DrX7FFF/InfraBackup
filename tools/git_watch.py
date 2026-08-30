"""tools/git_watch.py — Surveillance de l'état des repos Git distants."""

import sys
from pathlib import Path

from tools import runner


def _parse_git_status(repo: str, raw: str) -> tuple[bool, str]:
    """Parse la sortie de 'git status --short --branch' et retourne (has_issues, texte_rapport)."""
    status_lines = raw.splitlines()
    if not status_lines:
        return False, f"ERROR {repo} (pas de sortie)\n"

    branch_line = status_lines[0]   # ex: ## main...origin/main [ahead 1, behind 2]
    file_lines  = status_lines[1:]  # fichiers modifiés/non suivis

    has_ahead  = "ahead"  in branch_line
    has_behind = "behind" in branch_line
    has_files  = bool(file_lines)

    if not (has_ahead or has_behind or has_files):
        return False, f"OK {repo}\n"

    report = [f"ISSUES {repo}"]
    if has_files:
        report.append("  [uncommitted]")
        report.extend(f"    {l}" for l in file_lines)
    if has_ahead:
        report.append("  [not pushed]")
    if has_behind:
        report.append("  [not pulled]")

    return True, "\n".join(report) + "\n"


def run_git_watch(host: str, user: str, output_dir: Path, repos: list[str]) -> bool:
    """Vérifie l'état de chaque repo Git et écrit le résultat dans reports/git-status.txt.

    Retourne True si au moins un repo a des problèmes, False sinon.
    """
    reports_dir = output_dir / "reports"
    runner.mkdir(reports_dir)

    lines: list[str] = []
    any_issue = False

    for repo in repos:
        print(f"  [git] {repo}")

        cmd = f"git -C {repo} fetch --quiet 2>/dev/null; git -C {repo} status --short --branch"

        result = runner.run_cmd(host, user, cmd, capture_output=True, text=True)

        has_issues, report = _parse_git_status(repo, result.stdout)
        lines.append(report)
        if has_issues:
            any_issue = True

    runner.write_text(reports_dir / "git-status.txt", "\n".join(lines))
    return any_issue
