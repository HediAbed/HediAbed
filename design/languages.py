import json
import subprocess
from collections import Counter
from pathlib import Path

DESIGN = Path(__file__).resolve().parent
OWNER = "HediAbed"
EXCLUDED_REPOS = frozenset({"HediAbed", "uda-connect", "udacity_tech_trends"})
TOP_LANGUAGES = 5
REPO_LIMIT = "200"


def gh_json(*args: str) -> object:
    result = subprocess.run(["gh", *args], check=True, capture_output=True, text=True)
    return json.loads(result.stdout)


def own_public_repos() -> list[str]:
    repos = gh_json(
        "repo", "list", OWNER, "--visibility", "public", "--source", "--limit", REPO_LIMIT, "--json", "name"
    )
    return sorted(repo["name"] for repo in repos if repo["name"] not in EXCLUDED_REPOS)


def language_bytes(repos: list[str]) -> Counter[str]:
    totals: Counter[str] = Counter()
    for repo in repos:
        totals.update(gh_json("api", f"repos/{OWNER}/{repo}/languages"))
    return totals


def main() -> None:
    repos = own_public_repos()
    totals = language_bytes(repos)
    snapshot = {
        "repos": repos,
        "totalBytes": sum(totals.values()),
        "languages": [[name, count] for name, count in totals.most_common(TOP_LANGUAGES)],
    }
    (DESIGN / "languages.json").write_text(json.dumps(snapshot, indent=2) + "\n")


if __name__ == "__main__":
    main()
