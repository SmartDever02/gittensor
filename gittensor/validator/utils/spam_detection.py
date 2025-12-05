import re
from typing import List, Optional
from Levenshtein import distance, ratio
from gittensor.constants import (
    TYPO_MAX_DIST,
    TYPO_MIN_SIM,
    COMMENT_PATTERNS,
    PREPROCESSOR_LANGUAGES,
)

def tokenize(text: str) -> List[str]:
    return re.findall(r"[A-Za-z0-9_'-]+", text)

def token_pair_typo(o: str, n: str, max_dist: int, min_sim: float) -> bool:
    dist = distance(o, n)
    sim = ratio(o, n)
    return dist <= max_dist or sim >= min_sim

def is_token_typo(old: str, new: str, max_dist=TYPO_MAX_DIST, min_sim=TYPO_MIN_SIM) -> bool:
    """Check if two lines are likely typo corrections of each other."""
    old_tokens = tokenize(old)
    new_tokens = tokenize(new)

    if len(old_tokens) != len(new_tokens):
        return False

    return all(token_pair_typo(o, n, max_dist, min_sim)
            for o, n in zip(old_tokens, new_tokens))

def is_comment_line(content: str, file_extension: Optional[str] = None) -> bool:
    """Check if line content matches a comment pattern. Skips '#' pattern for preprocessor languages (C, C++, Rust, etc.) to avoid false positives."""
    patterns_to_check = COMMENT_PATTERNS
    if file_extension and file_extension in PREPROCESSOR_LANGUAGES:
        # Skip the '#' pattern (index 0) for languages where # is preprocessor directive
        patterns_to_check = [p for p in COMMENT_PATTERNS if not p.startswith(r'^\s*#')]
    
    return any(re.match(pattern, content) for pattern in patterns_to_check)

def looks_like_code(content: str) -> bool:
    """Check if content looks like actual code (not comment continuation)."""
    stripped = content.strip()
    if not stripped:
        return False
    
    # Common code patterns: operators, assignments, function calls, etc.
    code_indicators = [
        r'[=+\-*/%<>!&|]',  # Operators
        r'\(',               # Function calls
        r'\[',               # Indexing
        r'\{',               # Dict/set literals
        r'\.\w+',            # Method calls
        r'^\w+\s*=',         # Variable assignment
        r'^(if|for|while|def|class|return|import|from)\s',  # Keywords
    ]
    
    return any(re.search(pattern, stripped) for pattern in code_indicators)

def count_non_scoreable_lines(patch: str, max_scoreable_lines: Optional[int] = None, file_extension: Optional[str] = None) -> int:
    """Count lines that shouldn't contribute to the score (blank, comment, etc)."""
    if not patch:
        return 0
    
    non_scoreable = 0
    lines = patch.split("\n")
    scoreable_count = 0
    skip_next = False
    in_comment_block = False
    
    for i, line in enumerate(lines):
        if skip_next:
            skip_next = False
            in_comment_block = False
            continue
            
        if not is_single_diff_line(line):
            in_comment_block = False
            continue
        
        content = line[1:]
        is_comment = is_comment_line(content, file_extension)
        
        # Skip continuation lines (don't count as non-scoreable to prevent exploit)
        if in_comment_block and not is_comment and not looks_like_code(content):
            # Reset if next line is comment or code, otherwise stay in block
            if i + 1 < len(lines):
                next_line = lines[i + 1]
                if is_single_diff_line(next_line) and next_line.startswith("+"):
                    next_content = next_line[1:]
                    if is_comment_line(next_content, file_extension) or looks_like_code(next_content):
                        in_comment_block = False
            else:
                in_comment_block = False
            continue
        
        # Blank lines and comments
        if content.strip() == "" or is_comment:
            non_scoreable += 1
            in_comment_block = False  # Reset on blank or new comment
            # Check if next line might be a continuation
            if is_comment and line.startswith("+") and i + 1 < len(lines):
                next_line = lines[i + 1]
                if is_single_diff_line(next_line) and next_line.startswith("+"):
                    next_content = next_line[1:]
                    if not is_comment_line(next_content, file_extension) and not looks_like_code(next_content) and next_content.strip():
                        in_comment_block = True
            continue
        
        # Typo corrections: deletion followed by similar addition
        if line.startswith("-") and i + 1 < len(lines):
            next_line = lines[i + 1]
            if is_single_diff_line(next_line) and next_line.startswith("+"):
                if is_token_typo(content, next_line[1:]):
                    non_scoreable += 2
                    skip_next = True
                    in_comment_block = False
                    continue
        
        # This line is scoreable
        scoreable_count += 1
        if max_scoreable_lines is not None and scoreable_count >= max_scoreable_lines:
            break

    return non_scoreable

def is_single_diff_line(line: str) -> bool:
    """True for +foo or -bar but False for ++foo, --bar, etc."""
    if not line:
        return False
    char = line[0]
    return char in "+-" and (len(line) == 1 or line[1] != char)