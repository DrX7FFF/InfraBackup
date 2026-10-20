"""tools/git_watch.py — Surveillance de l'état des repos Git distants."""

from pathlib import Path

from tools import runner


def _parse_git_status(
    repo: str, raw: str, extra: list[str] | None = None
) -> tuple[bool, str]:
    """Parse la sortie de 'git status --short --branch' et retourne (has_issues, texte_rapport).

    extra : problèmes déjà formatés hors branche courante (fetch, tags, stash, autres branches).
    """
    status_lines = raw.splitlines()
    if not status_lines:
        return False, f"ERROR {repo} (pas de sortie)\n"

    branch_line = status_lines[0]  # ex: ## main...origin/main [ahead 1, behind 2]
    file_lines = status_lines[1:]  # fichiers modifiés/non suivis

    has_ahead = "ahead" in branch_line
    has_behind = "behind" in branch_line
    has_files = bool(file_lines)
    no_upstream = "..." not in branch_line  # branche jamais poussée / repo sans remote

    if not (has_ahead or has_behind or has_files or no_upstream or extra):
        return False, f"OK {repo}\n"

    report = [f"ISSUES {repo}"]
    if has_files:
        report.append("  [uncommitted]")
        report.extend(f"    {l}" for l in file_lines)
    if has_ahead:
        report.append("  [not pushed]")
    if has_behind:
        report.append("  [not pulled]")
    if no_upstream:
        report.append("  [no upstream]")
    report.extend(extra or [])

    return True, "\n".join(report) + "\n"


def _other_issues(host: str, user: str, repo: str) -> list[str]:
    """Tags non poussés, stash et autres branches non synchronisées (invisibles dans git status)."""
    cmd = (
        f"cd {repo} && echo '#current'; git branch --show-current; echo '#tags'; git tag; "
        "echo '#remote'; git ls-remote --tags origin 2>/dev/null; echo '#stash'; git stash list; "
        "echo '#branches'; LC_ALL=C git for-each-ref refs/heads "
        "--format='%(refname:short)|%(upstream:short)|%(upstream:track)'"
    )
    out = runner.run_cmd(host, user, cmd, capture_output=True, text=True).stdout

    sections: dict[str, list[str]] = {}
    key = ""
    for line in out.splitlines():
        if line.startswith("#"):
            key = line[1:]
            sections[key] = []
        elif line.strip():
            sections[key].append(line)

    issues = []
    remote_tags = {
        l.split("refs/tags/", 1)[-1].removesuffix("^{}")
        for l in sections.get("remote", [])
    }
    if tags := [t for t in sections.get("tags", []) if t not in remote_tags]:
        issues.append(f"  [tags not pushed] {' '.join(tags)}")
    if stash := sections.get("stash"):
        issues.append(f"  [stash] {len(stash)}")
    current = (sections.get("current") or [""])[0]
    for b in sections.get("branches", []):
        name, upstream, track = b.split("|")
        if name != current and (not upstream or track):
            issues.append(f"  [branch {name}] {track or 'no upstream'}")
    return issues


def _expand_repos(host: str, user: str, repos: list[str]) -> list[str]:
    """Développe les chemins avec glob (*) en liste des repos Git qu'ils contiennent.

    - Chemin sans glob → conservé tel quel (doit être un repo).
    - Chemin avec glob → seuls les dossiers matchés contenant un .git sont retenus.
      Si rien ne matche, le motif est conservé pour apparaître en ERROR dans le rapport.
    """
    expanded: list[str] = []
    for path in repos:
        if "*" not in path:
            expanded.append(path)
            continue

        # Glob évalué par le shell (local ou distant) : ~ et * sont développés sur la machine cible
        cmd = f'for d in {path}/; do [ -e "$d.git" ] && echo "${{d%/}}"; done; true'
        result = runner.run_cmd(host, user, cmd, capture_output=True, text=True)
        found = result.stdout.splitlines()
        expanded.extend(found or [path])
    return list(dict.fromkeys(expanded))  # dédoublonne en gardant l'ordre


def run_git_watch(host: str, user: str, output_dir: Path, repos: list[str]) -> bool:
    """Vérifie l'état de chaque repo Git et écrit le résultat dans reports/git-status.txt.

    Les chemins avec glob (ex : "~/GIT/*") sont développés en repos Git de premier niveau.
    Retourne True si au moins un repo a des problèmes, False sinon.
    """
    reports_dir = output_dir / "reports"
    runner.mkdir(reports_dir)

    repos = _expand_repos(host, user, repos)

    lines: list[str] = []
    any_issue = False

    for repo in repos:
        print(f"  [git] {repo}")

        cmd = f"git -C {repo} fetch --quiet 2>/dev/null || echo fetch-failed >&2; LC_ALL=C git -C {repo} status --short --branch"  # LC_ALL=C : ahead/behind en anglais pour le parsing

        result = runner.run_cmd(host, user, cmd, capture_output=True, text=True)

        extra = ["  [fetch failed]"] if "fetch-failed" in result.stderr else []
        extra += _other_issues(host, user, repo)
        has_issues, report = _parse_git_status(repo, result.stdout, extra)
        lines.append(report)
        if has_issues:
            any_issue = True

    runner.write_text(reports_dir / "git-status.txt", "\n".join(lines))
    return any_issue
