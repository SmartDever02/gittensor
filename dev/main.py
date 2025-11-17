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

# Output file
OUTPUT_FILE = ""

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
    
    # Validate configuration
    if GITHUB_PAT == "your_github_pat_here":
        print("❌ Please set GITHUB_PAT in the script!")
        sys.exit(1)
    
    # Start score calculation for the prs
    
    # Fetch all PR items
    pr_items = fetch_all_commits()
    print(f"Successfully fetched {len(pr_items)} PR items from dashboard")

    # Iterate through each PR entry
    for pr in pr_items:
        repo = pr["repository"]               # e.g. "cowrie/cowrie"
        pr_number = pr["pullRequestNumber"]   # PR number

        print("-" * 80)
        print(f"Processing Repository: {repo}")
        print(f"PR Number: {pr_number}")

        # Extract org and repo name
        org, repo_name = repo.split("/")

        # Output folder structure: output/<org>/
        output_dir = Path(f"output/{org}")
        output_dir.mkdir(parents=True, exist_ok=True)

        # File name: <repo>-<pr_number>.json
        OUTPUT_FILE = output_dir / f"{repo_name}-{pr_number}.json"

        print(f"Output File: {OUTPUT_FILE}")

        # Calculate score
        result = calculate_pr_score(
            repo,
            pr_number,
            GITHUB_PAT,
            programming_languages,
            master_repositories,
        )
        
        ## Add analytics
        result["analytics"]["original_score"] = float(pr["score"])

        # Check for errors
        if "error" in result:
            print(f"❌ Error scoring PR {repo}#{pr_number}: {result['error']}")
            continue

        # Save to JSON file
        with open(OUTPUT_FILE, 'w') as f:
            json.dump(result, f, indent=2)

        print(f"✓ Saved result to: {OUTPUT_FILE.absolute()}")

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