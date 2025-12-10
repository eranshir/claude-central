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
    return project_path.replace("/", "-")


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


def load_session_data(project_path: str, session_id: str) -> dict:
    """Load session data including summaries and messages."""
    slug = get_project_slug(project_path)
    session_dir = PROJECTS_DIR / slug
    session_file = session_dir / f"{session_id}.jsonl"

    data = {
        "summaries": [],
        "user_messages": [],
        "assistant_messages": [],
        "tool_calls": [],
        "file_changes": [],
        "first_timestamp": None,
        "last_timestamp": None,
    }

    if not session_file.exists():
        return data

    with open(session_file, 'r') as f:
        for line in f:
            try:
                entry = json.loads(line.strip())
                entry_type = entry.get("type")
                timestamp = parse_timestamp(entry.get("timestamp"))

                if timestamp:
                    if not data["first_timestamp"] or timestamp < data["first_timestamp"]:
                        data["first_timestamp"] = timestamp
                    if not data["last_timestamp"] or timestamp > data["last_timestamp"]:
                        data["last_timestamp"] = timestamp

                if entry_type == "summary":
                    data["summaries"].append(entry.get("summary", ""))
                elif entry_type == "user":
                    msg = entry.get("message", {})
                    content = msg.get("content", "")
                    if isinstance(content, str) and content.strip():
                        data["user_messages"].append({
                            "content": content,
                            "timestamp": timestamp.isoformat() if timestamp else None
                        })
                elif entry_type == "assistant":
                    msg = entry.get("message", {})
                    content = msg.get("content", [])
                    for item in (content if isinstance(content, list) else [content]):
                        if isinstance(item, dict):
                            if item.get("type") == "tool_use":
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
            except json.JSONDecodeError:
                continue

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
            if session_id not in projects[project_path]["sessions"]:
                projects[project_path]["sessions"][session_id] = {
                    "date": date_key,
                    "prompts": [],
                }
            projects[project_path]["sessions"][session_id]["prompts"].append({
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
                "days": {}
            }

        # Get git commits and tags for the project
        commits = get_git_commits_for_project(project_path)
        tags = get_git_tags_for_project(project_path)

        # Process each session
        for session_id, session_meta in project_info["sessions"].items():
            session_hash = f"{project_path}:{session_id}"

            # Skip already processed sessions unless force refresh
            if session_hash in processed_sessions and not force_refresh:
                continue

            date_key = session_meta["date"]

            # Load detailed session data
            session_data = load_session_data(project_path, session_id)

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
                "message_count": len(session_data["user_messages"]),
                "messages": [
                    {
                        "content": msg["content"][:1000],  # Truncate long messages
                        "timestamp": msg["timestamp"]
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
        project_path, session_id = session_hash.rsplit(":", 1)
        if project_path in projects:
            session_meta = projects[project_path]["sessions"].get(session_id)
            if session_meta:
                days_to_summarize.add((project_path, session_meta["date"]))

    for project_path, date_key in days_to_summarize:
        if project_path in output_data:
            project_name = output_data[project_path]["name"]
            day_data = output_data[project_path]["days"].get(date_key)
            if day_data and day_data["sessions"]:
                print(f"  {project_name} - {date_key}")
                day_data["summary"] = generate_daily_summary(
                    client, day_data["sessions"], project_name
                )

    # Save output
    final_output = {
        "projects": output_data,
        "last_updated": datetime.now().isoformat(),
        "processed_sessions": list(processed_sessions | set(new_processed))
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
