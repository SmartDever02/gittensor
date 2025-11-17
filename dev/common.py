import bittensor as bt
import requests

from gittensor.utils.github_api_tools import (
    get_pull_request_file_changes,
    make_headers
)
from gittensor.constants import BASE_GITHUB_API_URL

GITHUB_PAT = "YOUR_GITHUB_PAT"  # Replace with your GitHub PAT

def fetch_pr_from_rest_api(repository: str, pr_number: int, github_pat: str) -> dict:
    """
    Fetch PR data from GitHub REST API.
    
    Args:
        repository: Repository full name (owner/repo)
        pr_number: PR number
        github_pat: GitHub Personal Access Token
        
    Returns:
        dict: PR data from GitHub API or None if error
    """
    headers = make_headers(github_pat)
    
    try:
        # Fetch PR details
        response = requests.get(
            f'{BASE_GITHUB_API_URL}/repos/{repository}/pulls/{pr_number}',
            headers=headers,
            timeout=15
        )
        
        if response.status_code != 200:
            bt.logging.error(f"Failed to fetch PR: {response.status_code} - {response.text}")
            return None
            
        pr_data = response.json()
        bt.logging.info(f"Successfully fetched PR #{pr_number} from {repository}")
        return pr_data
        
    except Exception as e:
        bt.logging.error(f"Error fetching PR data: {e}")
        return None


def fetch_pr_issues(repository: str, pr_number: int, github_pat: str) -> list:
    """
    Fetch issues closed by this PR using GitHub timeline API.
    
    Args:
        repository: Repository full name
        pr_number: PR number
        github_pat: GitHub PAT
        
    Returns:
        list: List of Issue objects
    """
    headers = make_headers(github_pat)
    issues = []
    
    try:
        # Get timeline events to find closed issues
        response = requests.get(
            f'{BASE_GITHUB_API_URL}/repos/{repository}/issues/{pr_number}/timeline',
            headers={**headers, 'Accept': 'application/vnd.github.mockingbird-preview+json'},
            timeout=15
        )
        
        if response.status_code != 200:
            bt.logging.warning(f"Could not fetch timeline: {response.status_code}")
            return []
        
        timeline = response.json()
        
        # Find cross-referenced issues that were closed
        for event in timeline:
            if event.get('event') == 'cross-referenced':
                source = event.get('source', {})
                if source.get('type') == 'issue' and source.get('issue'):
                    issue_data = source['issue']
                    
                    # Only include closed issues
                    if issue_data.get('state') == 'closed':
                        issue = Issue(
                            number=issue_data['number'],
                            pr_number=pr_number,
                            repository_full_name=repository,
                            title=issue_data['title'],
                            created_at=parse_github_timestamp(issue_data.get('created_at')),
                            closed_at=parse_github_timestamp(issue_data.get('closed_at')),
                            author_login=issue_data.get('user', {}).get('login'),
                            state='CLOSED'
                        )
                        issues.append(issue)
        
        bt.logging.info(f"Found {len(issues)} closed issues for PR #{pr_number}")
        return issues
        
    except Exception as e:
        bt.logging.warning(f"Error fetching PR issues: {e}")
        return []


def convert_rest_pr_to_graphql_format(pr_data: dict, repository: str, issues: list) -> dict:
    """
    Convert REST API PR data to GraphQL format expected by PullRequest.from_graphql_response().
    
    Args:
        pr_data: PR data from REST API
        repository: Repository full name
        issues: List of Issue objects
        
    Returns:
        dict: PR data in GraphQL format
    """
    owner, repo_name = repository.split('/')
    
    # Convert issues to GraphQL format
    graphql_issues = []
    for issue in issues:
        graphql_issues.append({
            'number': issue.number,
            'title': issue.title,
            'state': issue.state,
            'createdAt': issue.created_at.isoformat() if issue.created_at else None,
            'closedAt': issue.closed_at.isoformat() if issue.closed_at else None,
            'author': {'login': issue.author_login} if issue.author_login else None
        })
    
    # Build GraphQL-like structure
    graphql_pr = {
        'number': pr_data['number'],
        'title': pr_data['title'],
        'additions': pr_data.get('additions', 0),
        'deletions': pr_data.get('deletions', 0),
        'mergedAt': pr_data.get('merged_at'),
        'createdAt': pr_data.get('created_at'),
        'lastEditedAt': pr_data.get('updated_at'),
        'bodyText': pr_data.get('body', ''),
        'state': pr_data['state'].upper(),
        'commits': {'totalCount': pr_data.get('commits', 0)},
        'repository': {
            'name': repo_name,
            'owner': {'login': owner},
            'defaultBranchRef': {
                'name': pr_data.get('base', {}).get('ref', 'main')
            }
        },
        'baseRefName': pr_data.get('base', {}).get('ref', 'main'),
        'author': {'login': pr_data.get('user', {}).get('login', 'unknown')},
        'mergedBy': {'login': pr_data.get('merged_by', {}).get('login')} if pr_data.get('merged_by') else None,
        'closingIssuesReferences': {
            'nodes': graphql_issues
        }
    }
    
    return graphql_pr

# Fetch all prs from gittensor.io api
def fetch_all_commits(base_url="https://api.gittensor.io/dash/commits", limit=15):
    page = 1
    all_items = []

    while True:
        response = requests.get(base_url, params={"page": page, "limit": limit})
        response.raise_for_status()

        items = response.json()   # <-- API returns a raw list

        if not items:             # Stop when API returns an empty array
            break

        all_items.extend(items)
        page += 1

    return all_items
