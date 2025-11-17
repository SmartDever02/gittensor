import json
import sys
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import bittensor as bt
from score import calculate_pr_score
from common import (
    GITHUB_PAT
)
from gittensor.validator.utils.load_weights import (
    load_programming_language_weights,
    load_master_repo_weights
)

# ============================================================================
# CONFIGURATION
# ============================================================================
REPOSITORY = "entrius/gittensor"             # e.g., "bitcoin/bitcoin"
# REPOSITORY = "happyfish100/fastdfs"             # e.g., "bitcoin/bitcoin"
PR_NUMBER = 20                       # PR number to score
# PR_NUMBER = 793                       # PR number to score


# Output file
OUTPUT_FILE = ""
# ============================================================================


def main():
    """Main execution function."""
    bt.logging.info("=" * 80)
    bt.logging.info("PR SCORE CALCULATOR - Using Validator's Exact Logic")
    bt.logging.info("=" * 80)
    
    # Validate configuration
    if GITHUB_PAT == "your_github_pat_here":
        bt.logging.error("❌ Please set GITHUB_PAT in the script!")
        sys.exit(1)
    
    bt.logging.info(f"Repository: {REPOSITORY}")
    bt.logging.info(f"PR Number: {PR_NUMBER}")
    OUTPUT_FILE = "output/" + str(REPOSITORY) + "-" + str(PR_NUMBER) + ".json"
    bt.logging.info(f"Output File: {OUTPUT_FILE}")
    bt.logging.info("-" * 80)
    
    # Load weights
    bt.logging.info("Loading language and repository weights...")
    programming_languages = load_programming_language_weights()
    master_repositories = load_master_repo_weights()
    
    if not programming_languages:
        bt.logging.error("❌ Failed to load programming language weights!")
        sys.exit(1)
    
    if not master_repositories:
        bt.logging.warning("⚠️  Failed to load master repository weights - using default weight 0.01")
        master_repositories = {}
    
    bt.logging.info(f"✓ Loaded {len(programming_languages)} language weights")
    bt.logging.info(f"✓ Loaded {len(master_repositories)} repository weights")
    bt.logging.info("-" * 80)
    
    # Calculate score
    result = calculate_pr_score(
        REPOSITORY,
        PR_NUMBER,
        GITHUB_PAT,
        programming_languages,
        master_repositories,
    )
    
    # Check for errors
    if "error" in result:
        bt.logging.error(f"❌ {result['error']}")
        sys.exit(1)
    
    # Print results to console
    bt.logging.info("\n" + "=" * 80)
    bt.logging.info("RESULTS")
    bt.logging.info("=" * 80)
    print(json.dumps(result, indent=2))
    
    # Save to JSON file
    output_path = Path(OUTPUT_FILE)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w') as f:
        json.dump(result, f, indent=2)
    
    bt.logging.info(f"\n✓ Results saved to: {output_path.absolute()}")
    bt.logging.info("=" * 80)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        bt.logging.info("\n⚠️  Script interrupted by user")
        sys.exit(0)
    except Exception as e:
        bt.logging.error(f"❌ Script failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)