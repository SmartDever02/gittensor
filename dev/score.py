#!/usr/bin/env python3
# The MIT License (MIT)
# Copyright © 2025 Entrius

"""
PR Score Calculator Script - Uses Validator's Exact Logic

Calculates the score for a given PR using the same methods validators use.
Supports both base scoring and full scoring with all multipliers.

Usage:
    python dev/calculate_pr_score.py

Configuration:
    - Set GITHUB_PAT, REPOSITORY, PR_NUMBER in the script
"""

import json
import sys
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import bittensor as bt
import requests

from gittensor.classes import PullRequest, MinerEvaluation, Issue

from gittensor.validator.evaluation.reward import score_pull_requests
from gittensor.validator.evaluation.scoring import (
    apply_time_decay_for_repository_contributions,
    apply_boost_for_gittensor_tag_in_pr_description,
    apply_repository_uniqueness_boost
)
from gittensor.validator.utils.load_weights import (
    load_programming_language_weights,
    load_master_repo_weights
)
from common import (
    GITHUB_PAT,
    fetch_pr_from_rest_api,
    fetch_pr_issues,
    convert_rest_pr_to_graphql_format
)
from gittensor.validator.utils.datetime_utils import parse_github_timestamp


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

def calculate_pr_score(
    repository: str,
    pr_number: int,
    github_pat: str,
    programming_languages: dict,
    master_repositories: dict,
) -> dict:
    """
    Calculate PR score using validator's exact logic.
    
    Args:
        repository: Repository full name
        pr_number: PR number
        github_pat: GitHub PAT
        programming_languages: Language weights
        master_repositories: Repository weights
        
    Returns:
        dict: Complete score breakdown
    """
    bt.logging.info(f"Calculating score for PR #{pr_number} in {repository}")
    bt.logging.info("=" * 80)
    
    # Step 1: Fetch PR data from GitHub REST API
    pr_data = fetch_pr_from_rest_api(repository, pr_number, github_pat)
    if not pr_data:
        return {"error": "Failed to fetch PR data from GitHub"}
    
    # Check if PR is merged
    if not pr_data.get('merged_at'):
        bt.logging.warning("⚠️  PR is not merged yet!")
    
    # Step 2: Fetch issues closed by this PR
    issues = fetch_pr_issues(repository, pr_number, github_pat)
    
    # Step 3: Convert REST API format to GraphQL format
    graphql_pr = convert_rest_pr_to_graphql_format(pr_data, repository, issues)
    
    # Step 4: Create MinerEvaluation object
    miner_eval = MinerEvaluation(
        uid=0,  # Not applicable for standalone script
        hotkey="standalone_script",
        github_id="standalone_script",
        github_pat=github_pat
    )
    
    # Step 5: Use validator's score_pull_requests() function
    # This is the EXACT function validators use (lines 30-91 in reward.py)
    miner_eval = score_pull_requests(
        uid=0,
        miner_eval=miner_eval,
        valid_raw_prs=[graphql_pr],  # List with single PR
        master_repositories=master_repositories,
        programming_languages=programming_languages
    )
    
    if not miner_eval.pull_requests:
        return {
            "error": "No valid PRs after scoring",
            "pr_number": pr_number,
            "repository": repository
        }
    
    pr = miner_eval.pull_requests[0]
    base_score = pr.earned_score
    
    bt.logging.info(f"✓ Base score calculated: {base_score:.5f}")
    
    # Step 6: Apply additional multipliers if full mode
    bt.logging.info("\nApplying additional multipliers...")
    
    # Create dict for scoring functions (they expect Dict[int, MinerEvaluation])
    miner_evals_dict = {0: miner_eval}
    
    # Apply time decay (lines 196 in reward.py)
    score_before_decay = pr.earned_score
    apply_time_decay_for_repository_contributions(miner_evals_dict)
    score_after_decay = pr.earned_score
    time_decay_multiplier = score_after_decay / score_before_decay if score_before_decay > 0 else 1.0
    bt.logging.info(f"✓ Time decay applied: {time_decay_multiplier:.4f}")
    
    # Apply Gittensor tag boost (lines 199 in reward.py)
    score_before_tag = pr.earned_score
    apply_boost_for_gittensor_tag_in_pr_description(miner_evals_dict)
    score_after_tag = pr.earned_score
    tag_multiplier = score_after_tag / score_before_tag if score_before_tag > 0 else 1.0
    bt.logging.info(f"✓ Gittensor tag boost applied: {tag_multiplier:.2f}")
    
    final_score = pr.earned_score
    
    # Step 7: Build result
    result = {
        "pr_number": pr_number,
        "repository": repository,
        "title": pr.title,
        "author": pr.author_login,
        "merged_at": pr.merged_at.isoformat() if pr.merged_at else None,
        "created_at": pr.created_at.isoformat(),
        "merged_by": pr.merged_by_login,
        "additions": pr.additions,
        "deletions": pr.deletions,
        "total_changes": pr.total_changes,
        "total_lines_scored": pr.total_lines_scored,
        "file_count": len(pr.file_changes) if pr.file_changes else 0,
        "issues_resolved": len(pr.issues) if pr.issues else 0,
        "scoring_breakdown": {
            "base_score": round(base_score, 5),
        },
        "file_changes": [
            {
                "filename": fc.filename,
                "extension": fc.file_extension,
                "changes": fc.changes,
                "additions": fc.additions,
                "deletions": fc.deletions,
                "status": fc.status,
                "language_weight": programming_languages.get(fc.file_extension, 0.12)
            }
            for fc in (pr.file_changes or [])
        ]
    }
    
    result["scoring_breakdown"]["time_decay_multiplier"] = round(time_decay_multiplier, 4)
    result["scoring_breakdown"]["gittensor_tag_multiplier"] = round(tag_multiplier, 2)
    result["scoring_breakdown"]["final_score"] = round(final_score, 5)
    result["scoring_breakdown"]["days_since_merge"] = round(
        (datetime.now(timezone.utc) - pr.merged_at).total_seconds() / 86400, 1
    ) if pr.merged_at else None
    result["scoring_breakdown"]["has_gittensor_tag"] = pr.gittensor_tagged
    
    return result
