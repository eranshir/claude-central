#!/usr/bin/env python3
"""
Claude Code History Analyzer

Scans Claude Code history files and generates structured summaries
of work done across projects, with optional GitHub commit linking.

Usage:
    python claude_history_analyzer.py [--output history.json] [--force-refresh]
"""

import json
import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
import hashlib
import argparse


def load_dotenv():
    """Load environment variables from .env file if it exists."""
    env_file = Path(__file__).parent / ".env"
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    # Remove quotes if present
                    value = value.strip().strip('"').strip("'")
                    os.environ.setdefault(key.strip(), value)


# Load .env file before importing anthropic
load_dotenv()

# Anthropic API for summarization
try:
    import anthropic
except ImportError:
    print("Please install anthropic: pip install anthropic")
    sys.exit(1)


CLAUDE_DIR = Path.home() / ".claude"
HISTORY_FILE = CLAUDE_DIR / "history.jsonl"
PROJECTS_DIR = CLAUDE_DIR / "projects"
DEFAULT_OUTPUT = Path.home() / "Documents/Projects/claudeHistory/history_data.json"


def parse_timestamp(ts) -> Optional[datetime]:
    """Parse various timestamp formats from Claude history."""
    if isinstance(ts, str):
        try:
            # ISO format
            return datetime.fromisoformat(ts.replace('Z', '+00:00'))
        except ValueError:
            pass
    elif isinstance(ts, (int, float)):
        # Unix timestamp in milliseconds (Claude uses 13+ digit timestamps)
        if ts > 1e12:
            ts = ts / 1000
        try:
            return datetime.fromtimestamp(ts)
        except (ValueError, OSError):
            pass
    return None


def get_project_slug(project_path: str) -> str:
    """Convert project path to Claude's slug format."""
    return project_path.replace("/", "-").replace("_", "-")


def get_project_name(project_path: str) -> str:
    """Extract clean project name from path."""
    return Path(project_path).name


def load_history_entries() -> list[dict]:
    """Load all entries from history.jsonl."""
    entries = []
    if not HISTORY_FILE.exists():
        print(f"History file not found: {HISTORY_FILE}")
        return entries

    with open(HISTORY_FILE, 'r') as f:
        for line in f:
            try:
                entry = json.loads(line.strip())
                entries.append(entry)
            except json.JSONDecodeError:
                continue
    return entries


def load_session_data(project_path: str, session_id: str, date_filter: str = None) -> dict:
    """Load session data including summaries and messages with assistant responses.

    Args:
        project_path: Path to the project
        session_id: Session UUID
        date_filter: Optional date string (YYYY-MM-DD) to filter entries to a specific day
    """
    slug = get_project_slug(project_path)
    session_dir = PROJECTS_DIR / slug
    session_file = session_dir / f"{session_id}.jsonl"

    data = {
        "summaries": [],
        "user_messages": [],
        "conversations": [],  # Paired user messages with assistant responses
        "assistant_messages": [],
        "tool_calls": [],
        "file_changes": [],
        "first_timestamp": None,
        "last_timestamp": None,
    }

    if not session_file.exists():
        return data

    # First pass: collect all entries with timestamps
    entries = []
    with open(session_file, 'r') as f:
        for line in f:
            try:
                entry = json.loads(line.strip())
                entry_type = entry.get("type")
                timestamp = parse_timestamp(entry.get("timestamp"))

                # Skip entries that don't match the date filter
                if date_filter:
                    if not timestamp:
                        continue  # Skip entries without timestamps when filtering by date
                    entry_date = timestamp.strftime("%Y-%m-%d")
                    if entry_date != date_filter:
                        continue

                entries.append((entry, timestamp))

                if timestamp:
                    if not data["first_timestamp"] or timestamp < data["first_timestamp"]:
                        data["first_timestamp"] = timestamp
                    if not data["last_timestamp"] or timestamp > data["last_timestamp"]:
                        data["last_timestamp"] = timestamp

            except json.JSONDecodeError:
                continue

    # Second pass: collect summaries and meaningful user messages only
    # Filter out: continuation summaries, short approvals, tool confirmations
    SKIP_PATTERNS = [
        "This session is being continued from a previous conversation",
        "Analysis:",
        "Summary:",
        "<system-reminder>",
        "<command-message>",
        "<command-name>",
    ]
    SHORT_APPROVAL_PHRASES = ["ok", "yes", "no", "continue", "done", "thanks", "thank you", "got it", "sure"]

    def is_meaningful_user_message(content: str) -> bool:
        """Check if a user message is meaningful (not a continuation or short approval)."""
        if not content or not content.strip():
            return False
        content_stripped = content.strip()
        # Skip continuation summaries and system content
        for pattern in SKIP_PATTERNS:
            if pattern in content_stripped:
                return False
        # Skip very short approval messages
        content_lower = content_stripped.lower()
        if len(content_stripped) < 50 and content_lower in SHORT_APPROVAL_PHRASES:
            return False
        # Skip if it's mostly just whitespace or too short
        if len(content_stripped) < 10:
            return False
        return True

    for entry, timestamp in entries:
        entry_type = entry.get("type")

        if entry_type == "summary":
            data["summaries"].append(entry.get("summary", ""))

        elif entry_type == "user":
            # Only capture meaningful user messages
            msg = entry.get("message", {})
            content = msg.get("content", "")
            if isinstance(content, str) and is_meaningful_user_message(content):
                user_msg = {
                    "content": content,
                    "timestamp": timestamp.isoformat() if timestamp else None
                }
                data["user_messages"].append(user_msg)
                # Also add to conversations (without response pairing for simplicity)
                data["conversations"].append({
                    "user": user_msg,
                    "assistant_response": ""  # Don't pair - just show user message
                })

        elif entry_type == "assistant":
            # Extract tool calls from assistant messages
            msg = entry.get("message", {})
            content = msg.get("content", [])
            for item in (content if isinstance(content, list) else [content]):
                if isinstance(item, dict) and item.get("type") == "tool_use":
                    tool_name = item.get("name", "")
                    tool_input = item.get("input", {})
                    data["tool_calls"].append({
                        "name": tool_name,
                        "input": tool_input,
                        "timestamp": timestamp.isoformat() if timestamp else None
                    })

        elif entry_type == "file-history-snapshot":
            snapshot = entry.get("snapshot", {})
            if snapshot.get("trackedFileBackups"):
                data["file_changes"].append({
                    "files": list(snapshot["trackedFileBackups"].keys()),
                    "timestamp": timestamp.isoformat() if timestamp else None
                })

    # Legacy compatibility: keep user_messages populated
    if not data["user_messages"] and data["conversations"]:
        data["user_messages"] = [conv["user"] for conv in data["conversations"]]

    return data


def get_git_commits_for_project(project_path: str, since_date: Optional[datetime] = None) -> list[dict]:
    """Get git commits for a project directory."""
    commits = []

    if not Path(project_path).exists():
        return commits

    try:
        cmd = ["git", "-C", project_path, "log", "--pretty=format:%H|%s|%ai|%an", "-n", "500"]
        if since_date:
            cmd.extend(["--since", since_date.strftime("%Y-%m-%d")])

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            for line in result.stdout.strip().split('\n'):
                if line:
                    parts = line.split('|', 3)
                    if len(parts) >= 3:
                        commit_time = parse_timestamp(parts[2].strip())
                        commits.append({
                            "sha": parts[0],
                            "message": parts[1] if len(parts) > 1 else "",
                            "timestamp": commit_time.isoformat() if commit_time else None,
                            "author": parts[3] if len(parts) > 3 else ""
                        })
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    return commits


def get_github_remote(project_path: str) -> Optional[str]:
    """Get GitHub remote URL for a project."""
    try:
        result = subprocess.run(
            ["git", "-C", project_path, "remote", "get-url", "origin"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            url = result.stdout.strip()
            # Convert SSH to HTTPS format
            if url.startswith("git@github.com:"):
                url = url.replace("git@github.com:", "https://github.com/")
            if url.endswith(".git"):
                url = url[:-4]
            return url
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return None


def load_beads_issues(project_path: str) -> list[dict]:
    """Load beads issues from a project's .beads/issues.jsonl file."""
    beads_file = Path(project_path) / ".beads" / "issues.jsonl"
    issues = []

    if not beads_file.exists():
        return issues

    try:
        with open(beads_file, 'r') as f:
            for line in f:
                try:
                    issue = json.loads(line.strip())
                    # Parse timestamps
                    for ts_field in ['created_at', 'updated_at', 'closed_at']:
                        if issue.get(ts_field):
                            parsed = parse_timestamp(issue[ts_field])
                            if parsed:
                                issue[ts_field] = parsed.isoformat()
                    issues.append(issue)
                except json.JSONDecodeError:
                    continue
    except IOError:
        pass

    return issues


def get_beads_stats(issues: list[dict]) -> dict:
    """Calculate statistics from beads issues."""
    if not issues:
        return None

    open_issues = [i for i in issues if i.get('status') == 'open']
    closed_issues = [i for i in issues if i.get('status') == 'closed']

    # Count by type
    by_type = {}
    for issue in issues:
        issue_type = issue.get('issue_type', 'unknown')
        by_type[issue_type] = by_type.get(issue_type, 0) + 1

    # Count by priority
    by_priority = {}
    for issue in issues:
        priority = issue.get('priority', 0)
        by_priority[priority] = by_priority.get(priority, 0) + 1

    return {
        "total": len(issues),
        "open": len(open_issues),
        "closed": len(closed_issues),
        "by_type": by_type,
        "by_priority": by_priority
    }


def get_git_tags_for_project(project_path: str) -> dict[str, str]:
    """Get a mapping of commit SHA to tag name for a project."""
    sha_to_tag = {}

    if not Path(project_path).exists():
        return sha_to_tag

    try:
        # Get all tags with their commit SHAs
        result = subprocess.run(
            ["git", "-C", project_path, "tag", "-l", "--format=%(refname:short)|%(objectname)"],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            for line in result.stdout.strip().split('\n'):
                if line and '|' in line:
                    tag_name, sha = line.split('|', 1)
                    # For annotated tags, get the commit they point to
                    deref_result = subprocess.run(
                        ["git", "-C", project_path, "rev-parse", f"{tag_name}^{{commit}}"],
                        capture_output=True, text=True, timeout=10
                    )
                    if deref_result.returncode == 0:
                        commit_sha = deref_result.stdout.strip()
                        sha_to_tag[commit_sha] = tag_name
                    else:
                        sha_to_tag[sha] = tag_name
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    return sha_to_tag


def find_matching_commits(session_data: dict, commits: list[dict]) -> list[dict]:
    """Find commits that match the session's timeframe."""
    if not session_data["first_timestamp"] or not session_data["last_timestamp"]:
        return []

    # Add some buffer time around the session
    start = session_data["first_timestamp"] - timedelta(minutes=30)
    end = session_data["last_timestamp"] + timedelta(minutes=30)

    matching = []
    for commit in commits:
        commit_time = parse_timestamp(commit.get("timestamp"))
        if commit_time and start <= commit_time <= end:
            matching.append(commit)

    return matching


def generate_session_summary(client: Optional[anthropic.Anthropic], session_data: dict, project_name: str) -> str:
    """Use Claude to generate a summary of the session."""
    # First check if we have built-in summaries
    if session_data["summaries"]:
        return " | ".join(session_data["summaries"][:5])

    # If no API client, use simple fallback
    if client is None:
        if session_data["user_messages"]:
            # Create a simple summary from user messages
            first_msgs = [msg['content'][:100] for msg in session_data["user_messages"][:3]]
            return f"Session topics: {'; '.join(first_msgs)}"
        return "No activity recorded"

    # Otherwise, generate from user messages using API
    if not session_data["user_messages"]:
        return "No activity recorded"

    # Prepare context for summarization
    messages_text = "\n".join([
        f"- {msg['content'][:500]}"
        for msg in session_data["user_messages"][:30]
    ])

    tools_used = set()
    for tc in session_data["tool_calls"][:50]:
        tools_used.add(tc.get("name", "unknown"))

    prompt = f"""Analyze this Claude Code session for project "{project_name}" and create a concise bullet-point summary of what was accomplished.

User messages/requests during session:
{messages_text}

Tools used: {', '.join(tools_used) if tools_used else 'None recorded'}

Provide 2-5 bullet points summarizing the main activities and accomplishments. Be specific about what was done, not just what was discussed. Format as plain bullet points starting with "- "."""

    try:
        response = client.messages.create(
            model="claude-opus-4-5-20251101",  # Use Opus 4.5 for high-quality summaries
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text
    except Exception as e:
        print(f"  Warning: Claude API call failed: {e}")
        # Fallback to simple summary
        if session_data["summaries"]:
            return session_data["summaries"][0]
        return f"Session with {len(session_data['user_messages'])} messages"


def generate_daily_summary(client: Optional[anthropic.Anthropic], sessions: list[dict], project_name: str) -> str:
    """Generate a comprehensive daily summary from multiple sessions."""
    all_summaries = []
    all_commits = []

    for session in sessions:
        if session.get("summary"):
            all_summaries.append(session["summary"])
        all_commits.extend(session.get("commits", []))

    if not all_summaries:
        return "No significant activity"

    combined = "\n".join(all_summaries)

    # If no API client, just combine summaries
    if client is None:
        return combined[:500]

    commit_msgs = "\n".join([f"- {c['message']}" for c in all_commits[:10]])

    prompt = f"""Synthesize these session summaries into a concise daily summary for project "{project_name}":

Session summaries:
{combined}

Git commits made:
{commit_msgs if commit_msgs else "No commits recorded"}

Provide a brief 1-3 sentence summary of the day's work. Focus on concrete accomplishments."""

    try:
        response = client.messages.create(
            model="claude-opus-4-5-20251101",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text
    except Exception as e:
        print(f"  Warning: Daily summary generation failed: {e}")
        return combined[:500]


def generate_claude_md_suggestions(client: Optional[anthropic.Anthropic], output_data: dict) -> list[dict]:
    """
    Analyze history patterns and generate suggestions for CLAUDE.md instructions.

    These suggestions are based on:
    1. Patterns found in the user's coding history (common requests, repeated tasks)
    2. Best practices relevant to the types of projects the user is building
    """
    if client is None:
        return []

    # Gather context from all projects
    project_summaries = []
    all_tools = set()
    all_beads_types = set()
    project_types = []

    for project_path, project in output_data.items():
        project_name = project.get("name", "unknown")

        # Collect session summaries
        for date, day_data in project.get("days", {}).items():
            for session in day_data.get("sessions", []):
                if session.get("summary"):
                    project_summaries.append(f"[{project_name}] {session['summary'][:300]}")
                all_tools.update(session.get("tools_used", []))

        # Collect beads info
        if project.get("beads") and project["beads"].get("stats"):
            stats = project["beads"]["stats"]
            all_beads_types.update(stats.get("by_type", {}).keys())

        # Infer project type from name and path
        project_types.append(project_name)

    if not project_summaries:
        return []

    # Prepare prompt for Claude
    summaries_sample = "\n".join(project_summaries[:50])  # Limit to avoid token overflow
    tools_list = ", ".join(list(all_tools)[:30])

    prompt = f"""You are analyzing a developer's Claude Code usage history to suggest instructions they could add to their CLAUDE.md file. CLAUDE.md is a file that provides persistent instructions to Claude Code across all sessions.

## Developer's Projects
{', '.join(project_types[:15])}

## Sample of Recent Session Summaries
{summaries_sample}

## Tools Frequently Used
{tools_list}

## Issue Types Tracked (via Beads)
{', '.join(all_beads_types) if all_beads_types else 'None'}

---

Based on this developer's patterns and your knowledge of best practices, suggest 5-8 instructions they could add to their CLAUDE.md file. Each suggestion should:

1. Be actionable and specific
2. Help Claude Code better assist this specific developer
3. Either address a pattern you noticed OR introduce a best practice relevant to their project types

For each suggestion, provide:
- A short title (2-5 words)
- The actual instruction text (1-3 sentences, written as you would write in CLAUDE.md)
- A brief rationale explaining why this would help (1 sentence)

Format your response as JSON array:
```json
[
  {{
    "title": "Short Title",
    "instruction": "The actual instruction text to add to CLAUDE.md",
    "rationale": "Why this would help the developer"
  }}
]
```

Focus on practical, high-value suggestions. Consider things like:
- Code style preferences
- Testing requirements
- Documentation standards
- Error handling approaches
- Git commit conventions
- Project-specific patterns
- Language/framework best practices
- Security considerations
- Performance guidelines"""

    try:
        print("Generating CLAUDE.md suggestions...")
        response = client.messages.create(
            model="claude-opus-4-5-20251101",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}]
        )

        # Parse the JSON response
        response_text = response.content[0].text

        # Extract JSON from response (handle markdown code blocks)
        import re
        json_match = re.search(r'```json\s*([\s\S]*?)\s*```', response_text)
        if json_match:
            json_str = json_match.group(1)
        else:
            # Try to find raw JSON array
            json_match = re.search(r'\[[\s\S]*\]', response_text)
            if json_match:
                json_str = json_match.group(0)
            else:
                print("  Warning: Could not parse suggestions JSON")
                return []

        suggestions = json.loads(json_str)
        print(f"  Generated {len(suggestions)} suggestions")
        return suggestions

    except Exception as e:
        print(f"  Warning: Failed to generate suggestions: {e}")
        return []


def load_existing_data(output_path: Path) -> dict:
    """Load existing history data if available."""
    if output_path.exists():
        try:
            with open(output_path, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {"projects": {}, "last_updated": None, "processed_sessions": []}


def get_session_hash(project_path: str, session_id: str, session_data: dict) -> str:
    """Create a hash to identify if a session has been processed."""
    content = f"{project_path}:{session_id}:{len(session_data.get('user_messages', []))}"
    return hashlib.md5(content.encode()).hexdigest()


def analyze_history(output_path: Path = DEFAULT_OUTPUT, force_refresh: bool = False, no_api: bool = False):
    """Main function to analyze Claude history and generate structured output."""
    print("Claude Code History Analyzer")
    print("=" * 40)

    # Initialize Anthropic client
    client = None
    if not no_api:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            print("Warning: ANTHROPIC_API_KEY not set. Using --no-api mode (built-in summaries only).")
            no_api = True
        else:
            client = anthropic.Anthropic(api_key=api_key)

    # Load existing data for incremental updates
    existing_data = load_existing_data(output_path) if not force_refresh else {"projects": {}, "processed_sessions": []}
    processed_sessions = set(existing_data.get("processed_sessions", []))

    print(f"Loading history from {HISTORY_FILE}...")
    entries = load_history_entries()
    print(f"Found {len(entries)} history entries")

    # Group entries by project and session
    projects = {}
    for entry in entries:
        project_path = entry.get("project")
        if not project_path:
            continue

        if project_path not in projects:
            projects[project_path] = {
                "name": get_project_name(project_path),
                "path": project_path,
                "sessions": {},
                "github_url": None,
            }

        session_id = entry.get("sessionId")
        timestamp = parse_timestamp(entry.get("timestamp"))

        if session_id and timestamp:
            date_key = timestamp.strftime("%Y-%m-%d")
            # Use session_id + date as key to handle multi-day sessions
            session_date_key = f"{session_id}:{date_key}"
            if session_date_key not in projects[project_path]["sessions"]:
                projects[project_path]["sessions"][session_date_key] = {
                    "session_id": session_id,
                    "date": date_key,
                    "prompts": [],
                }
            projects[project_path]["sessions"][session_date_key]["prompts"].append({
                "display": entry.get("display", ""),
                "timestamp": timestamp.isoformat()
            })

    print(f"Found {len(projects)} projects")

    # Process each project
    output_data = existing_data.get("projects", {})
    new_processed = []

    for project_path, project_info in projects.items():
        project_name = project_info["name"]
        print(f"\nProcessing: {project_name}")

        if project_path not in output_data:
            output_data[project_path] = {
                "name": project_name,
                "path": project_path,
                "github_url": get_github_remote(project_path),
                "days": {},
                "beads": None
            }

        # Load beads issues for this project
        beads_issues = load_beads_issues(project_path)
        if beads_issues:
            print(f"  Found {len(beads_issues)} beads issues")
            output_data[project_path]["beads"] = {
                "issues": beads_issues,
                "stats": get_beads_stats(beads_issues)
            }

        # Get git commits and tags for the project
        commits = get_git_commits_for_project(project_path)
        tags = get_git_tags_for_project(project_path)

        # Process each session (session_date_key is "session_id:date")
        for session_date_key, session_meta in project_info["sessions"].items():
            session_id = session_meta["session_id"]
            session_hash = f"{project_path}:{session_date_key}"

            # Skip already processed sessions unless force refresh
            if session_hash in processed_sessions and not force_refresh:
                continue

            date_key = session_meta["date"]

            # Load detailed session data, filtered to only this day's entries
            session_data = load_session_data(project_path, session_id, date_filter=date_key)

            if not session_data["user_messages"] and not session_data["summaries"]:
                continue

            print(f"  Session {session_id[:8]}... ({date_key})")

            # Generate summary
            summary = generate_session_summary(client, session_data, project_name)

            # Find matching commits
            matching_commits = find_matching_commits(session_data, commits)

            # Prepare session output
            session_output = {
                "session_id": session_id,
                "summary": summary,
                "message_count": len(session_data["conversations"]) or len(session_data["user_messages"]),
                "messages": [
                    {
                        "content": conv["user"]["content"][:1000],  # Truncate long messages
                        "timestamp": conv["user"]["timestamp"],
                        "assistant_response": conv.get("assistant_response", "")
                    }
                    for conv in session_data["conversations"]
                ] if session_data["conversations"] else [
                    {
                        "content": msg["content"][:1000],
                        "timestamp": msg["timestamp"],
                        "assistant_response": ""
                    }
                    for msg in session_data["user_messages"]
                ],
                "start_time": session_data["first_timestamp"].isoformat() if session_data["first_timestamp"] else None,
                "end_time": session_data["last_timestamp"].isoformat() if session_data["last_timestamp"] else None,
                "commits": [
                    {
                        "sha": c["sha"],
                        "message": c["message"],
                        "tag": tags.get(c["sha"]),
                        "url": (
                            f"{output_data[project_path].get('github_url')}/releases/tag/{tags[c['sha']]}"
                            if c["sha"] in tags and output_data[project_path].get('github_url')
                            else (
                                f"{output_data[project_path].get('github_url')}/commit/{c['sha']}"
                                if output_data[project_path].get('github_url')
                                else None
                            )
                        )
                    }
                    for c in matching_commits
                ],
                "tools_used": list(set(tc["name"] for tc in session_data["tool_calls"]))[:20]
            }

            # Add to output
            if date_key not in output_data[project_path]["days"]:
                output_data[project_path]["days"][date_key] = {
                    "sessions": [],
                    "summary": None
                }

            # Check if session already exists
            existing_sessions = output_data[project_path]["days"][date_key]["sessions"]
            existing_ids = {s["session_id"] for s in existing_sessions}
            if session_id not in existing_ids:
                existing_sessions.append(session_output)

            new_processed.append(session_hash)

    # Generate daily summaries for days with new sessions
    print("\nGenerating daily summaries...")
    days_to_summarize = set()
    for session_hash in new_processed:
        # session_hash is "project_path:session_id:date_key"
        parts = session_hash.rsplit(":", 2)
        if len(parts) == 3:
            project_path, _, date_key = parts[0], parts[1], parts[2]
            # Reconstruct from the original split point (project_path may contain colons on Windows)
            session_date_key = f"{parts[1]}:{parts[2]}"
            # Find where project_path ends by looking for the session_date_key
            idx = session_hash.rfind(f":{session_date_key}")
            if idx > 0:
                project_path = session_hash[:idx]
                days_to_summarize.add((project_path, date_key))

    for project_path, date_key in days_to_summarize:
        if project_path in output_data:
            project_name = output_data[project_path]["name"]
            day_data = output_data[project_path]["days"].get(date_key)
            if day_data and day_data["sessions"]:
                print(f"  {project_name} - {date_key}")
                day_data["summary"] = generate_daily_summary(
                    client, day_data["sessions"], project_name
                )

    # Generate CLAUDE.md suggestions
    suggestions = generate_claude_md_suggestions(client, output_data)

    # Save output
    final_output = {
        "projects": output_data,
        "last_updated": datetime.now().isoformat(),
        "processed_sessions": list(processed_sessions | set(new_processed)),
        "suggestions": suggestions
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w') as f:
        json.dump(final_output, f, indent=2)

    print(f"\nSaved to: {output_path}")
    print(f"Projects: {len(output_data)}")
    total_sessions = sum(
        len(day["sessions"])
        for proj in output_data.values()
        for day in proj.get("days", {}).values()
    )
    print(f"Total sessions: {total_sessions}")


def main():
    parser = argparse.ArgumentParser(description="Analyze Claude Code history")
    parser.add_argument(
        "--output", "-o",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Output JSON file path"
    )
    parser.add_argument(
        "--force-refresh", "-f",
        action="store_true",
        help="Force refresh all sessions (ignore cache)"
    )
    parser.add_argument(
        "--no-api",
        action="store_true",
        help="Skip API calls, use only built-in summaries from session files"
    )
    args = parser.parse_args()

    analyze_history(args.output, args.force_refresh, args.no_api)


if __name__ == "__main__":
    main()
