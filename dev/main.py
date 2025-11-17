import json
import sys
import os
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from score import calculate_pr_score
from common import (
    GITHUB_PAT,
    fetch_all_commits
)
from gittensor.validator.utils.load_weights import (
    load_programming_language_weights,
    load_master_repo_weights
)

# Output root folder
OUTPUT_ROOT = Path("output")
OVERVIEW_FILE = OUTPUT_ROOT / "overview.json"


def main():
    """Main execution function."""
    print("=" * 80)
    print("PR SCORE CALCULATOR - Using Validator's Exact Logic")
    print("=" * 80)

    # Load weights
    print("Loading language and repository weights...")
    programming_languages = load_programming_language_weights()
    master_repositories = load_master_repo_weights()

    if not programming_languages:
        print("❌ Failed to load programming language weights!")
        sys.exit(1)

    if not master_repositories:
        print("⚠️  Failed to load master repository weights - using default weight 0.01")
        master_repositories = {}

    print(f"✓ Loaded {len(programming_languages)} language weights")
    print(f"✓ Loaded {len(master_repositories)} repository weights")

    print("-" * 80)

    # Validate config
    if GITHUB_PAT == "your_github_pat_here":
        print("❌ Please set GITHUB_PAT in the script!")
        sys.exit(1)

    # Fetch PR items
    pr_items = fetch_all_commits()
    total_prs = len(pr_items)
    print(f"Successfully fetched {total_prs} PR items from dashboard")

    # ----------------------------------------------------------------------
    # 🔥 GLOBAL ANALYTICS AGGREGATION
    # ----------------------------------------------------------------------
    overview = {
        "total_prs": total_prs,
        "spam_passed": 0,
        "spam_failed": 0,
        "total_penalties": 0,
        "repos": {}   # per-repo stats
    }
    # ----------------------------------------------------------------------

    for pr in pr_items:
        repo = pr["repository"]
        pr_number = pr["pullRequestNumber"]

        print("-" * 80)
        print(f"Processing Repository: {repo}")
        print(f"PR Number: {pr_number}")

        org, repo_name = repo.split("/")

        # Output folder structure
        repo_out_dir = OUTPUT_ROOT / org
        repo_out_dir.mkdir(parents=True, exist_ok=True)

        pr_output_file = repo_out_dir / f"{repo_name}-{pr_number}.json"

        print(f"Output File: {pr_output_file}")

        # Score the PR
        result = calculate_pr_score(
            repo,
            pr_number,
            GITHUB_PAT,
            programming_languages,
            master_repositories,
        )

        # Add original dashboard score
        result["analytics"]["original_score"] = float(pr["score"])

        # Check for errors
        if "error" in result:
            print(f"❌ Error scoring PR {repo}#{pr_number}: {result['error']}")
            continue

        # ----------------------------------------------------------------------
        # 🔥 UPDATE GLOBAL ANALYTICS
        # ----------------------------------------------------------------------
        penalties = result["analytics"].get("penalties", [])
        repo_stats = overview["repos"].setdefault(repo, {"total": 0, "passed": 0, "failed": 0})

        repo_stats["total"] += 1
        overview["total_penalties"] += len(penalties)

        if len(penalties) == 0:
            overview["spam_passed"] += 1
            repo_stats["passed"] += 1
        else:
            overview["spam_failed"] += 1
            repo_stats["failed"] += 1
        # ----------------------------------------------------------------------

        # Save individual PR analytics
        with open(pr_output_file, 'w') as f:
            json.dump(result, f, indent=2)

        print(f"✓ Saved result to: {pr_output_file.absolute()}")

    # ----------------------------------------------------------------------
    # 🔥 WRITE FINAL OVERVIEW.JSON
    # ----------------------------------------------------------------------
    OUTPUT_ROOT.mkdir(exist_ok=True)
    with open(OVERVIEW_FILE, "w") as f:
        json.dump(overview, f, indent=2)

    print(f"\n\n📊 Overview saved to {OVERVIEW_FILE.absolute()}\n")
    print(json.dumps(overview, indent=2))

    print("=" * 80)
    print("🎉 Finished scoring all PRs")
    print("=" * 80)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n⚠️  Script interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"❌ Script failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
