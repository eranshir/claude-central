#!/usr/bin/env python3
"""
Simple HTTP server for Claude History Analyzer.

Serves static files and provides API endpoints for:
- Adding instructions to CLAUDE.md
- Real-time session monitoring
"""

import http.server
import json
import os
import socketserver
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

# CLAUDE.md location
CLAUDE_MD_PATH = Path.home() / ".claude" / "CLAUDE.md"
CLAUDE_PROJECTS_DIR = Path.home() / ".claude" / "projects"

PORT = 9347


class TerminalFocuser:
    """Focuses terminal windows by searching for project name in window/tab titles."""

    @staticmethod
    def _sanitize_applescript_string(text: str) -> str:
        """Sanitize a string for safe use in AppleScript to prevent injection."""
        if not text:
            return ""
        # Escape backslashes first, then quotes
        sanitized = text.replace("\\", "\\\\").replace('"', '\\"')
        # Remove any other potentially dangerous characters
        # Only allow alphanumeric, spaces, hyphens, underscores, and dots
        import re
        sanitized = re.sub(r'[^\w\s\-._]', '', sanitized)
        return sanitized

    @staticmethod
    def list_terminal_windows() -> list:
        """List all Terminal.app windows and extract project info."""
        import subprocess
        import re

        windows = []

        # Get all Terminal.app window names with their IDs (stable identifiers)
        script = '''
        tell application "System Events"
            if not (exists process "Terminal") then
                return ""
            end if
        end tell

        tell application "Terminal"
            set windowList to {}
            repeat with w in windows
                set windowId to id of w
                set windowName to name of w
                set end of windowList to (windowId as text) & "|||" & windowName
            end repeat
            return windowList
        end tell
        '''

        try:
            result = subprocess.run(
                ['osascript', '-e', script],
                capture_output=True,
                text=True,
                timeout=5
            )
            output = result.stdout.strip()

            if not output:
                return windows

            # Parse the output - it's comma-separated
            for item in output.split(", "):
                if "|||" not in item:
                    continue
                parts = item.split("|||")
                if len(parts) != 2:
                    continue

                window_id = parts[0].strip()  # This is the stable window ID
                window_name = parts[1].strip()

                # Check if it's a Claude-related window (contains "claude" or "node")
                is_claude = "claude" in window_name.lower() or "node" in window_name.lower()

                # Extract project name (first part before " — ")
                project_name = window_name.split(" — ")[0].strip() if " — " in window_name else window_name

                # Try to find the full path
                project_path = None
                for proj_dir in CLAUDE_PROJECTS_DIR.iterdir():
                    if proj_dir.is_dir() and project_name.lower() in proj_dir.name.lower():
                        # Reconstruct path from directory name
                        dir_name = proj_dir.name
                        if dir_name.startswith("-"):
                            project_path = "/" + "/".join(dir_name.split("-")[1:])
                        break

                windows.append({
                    "window_id": int(window_id),  # Stable window ID
                    "window_name": window_name,
                    "project_name": project_name,
                    "project_path": project_path,
                    "is_claude": is_claude
                })

        except Exception as e:
            print(f"Error listing terminal windows: {e}")

        # Sort by window_id for consistent ordering
        windows.sort(key=lambda w: w.get("window_id", 0))
        return windows

    @staticmethod
    def focus_by_index(window_index: int) -> dict:
        """Focus a Terminal window by its index (deprecated - use focus_by_id)."""
        import subprocess

        script = f'''
        tell application "Terminal"
            set w to window {window_index}
            set index of w to 1
            activate
            return name of w
        end tell
        '''

        try:
            result = subprocess.run(
                ['osascript', '-e', script],
                capture_output=True,
                text=True,
                timeout=5
            )
            output = result.stdout.strip()

            if output:
                return {"success": True, "terminal": "Terminal.app", "window_name": output}
            else:
                return {"success": False, "error": "Could not focus window"}

        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Timeout"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def focus_by_id(window_id: int) -> dict:
        """Focus a Terminal window by its stable ID."""
        import subprocess

        # Use Window menu to switch - this works even for full screen windows
        script = f'''
        set targetId to {window_id}
        set targetName to ""

        tell application "Terminal"
            -- Get the window name first
            try
                set targetName to name of window id targetId
            on error
                return "error:Window not found"
            end try

            -- Activate Terminal
            activate
            delay 0.2
        end tell

        -- Use the Window menu to select the specific window (works for fullscreen too)
        tell application "System Events"
            tell process "Terminal"
                -- Click Window menu
                click menu bar item "Window" of menu bar 1
                delay 0.1
                -- Try to click the exact window name
                try
                    click menu item targetName of menu "Window" of menu bar 1
                on error
                    -- Window might have a checkmark or other formatting, try contains
                    repeat with menuItem in menu items of menu "Window" of menu bar 1
                        try
                            if name of menuItem contains targetName then
                                click menuItem
                                exit repeat
                            end if
                        end try
                    end repeat
                end try
            end tell
        end tell

        return targetName
        '''

        try:
            result = subprocess.run(
                ['osascript', '-e', script],
                capture_output=True,
                text=True,
                timeout=10
            )
            output = result.stdout.strip()
            stderr = result.stderr.strip()

            if output.startswith("error:"):
                return {"success": False, "error": output[6:]}
            elif output and not stderr:
                return {"success": True, "terminal": "Terminal.app", "window_name": output, "window_id": window_id}
            else:
                return {"success": False, "error": stderr or "Could not focus window"}

        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Timeout"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def focus_terminal(search_term: str) -> dict:
        """
        Try to focus a terminal window containing the search term.
        Supports Terminal.app and iTerm2.
        """
        import subprocess
        import shutil

        # Try iTerm2 first (more common among developers)
        if shutil.which("osascript"):
            # Check if iTerm2 is running
            result = TerminalFocuser._try_iterm2(search_term)
            if result.get("success"):
                return result

            # Fall back to Terminal.app
            result = TerminalFocuser._try_terminal_app(search_term)
            if result.get("success"):
                return result

        return {
            "success": False,
            "error": f"Could not find terminal window containing '{search_term}'"
        }

    @staticmethod
    def _try_iterm2(search_term: str) -> dict:
        """Try to focus iTerm2 window/tab containing search term."""
        import subprocess

        # Sanitize search term to prevent AppleScript injection
        safe_search_term = TerminalFocuser._sanitize_applescript_string(search_term)

        # AppleScript to search iTerm2 windows and tabs
        script = f'''
        tell application "System Events"
            if not (exists process "iTerm2") then
                return "not_running"
            end if
        end tell

        tell application "iTerm2"
            set found to false
            repeat with w in windows
                repeat with t in tabs of w
                    repeat with s in sessions of t
                        set sessionName to name of s
                        if sessionName contains "{safe_search_term}" then
                            select t
                            select w
                            activate
                            return "found"
                        end if
                    end repeat
                end repeat
            end repeat
            return "not_found"
        end tell
        '''

        try:
            result = subprocess.run(
                ['osascript', '-e', script],
                capture_output=True,
                text=True,
                timeout=5
            )
            output = result.stdout.strip()

            if output == "found":
                return {"success": True, "terminal": "iTerm2", "project": search_term}
            elif output == "not_running":
                return {"success": False, "error": "iTerm2 not running"}
            else:
                return {"success": False, "error": "Not found in iTerm2"}

        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Timeout searching iTerm2"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def _try_terminal_app(search_term: str) -> dict:
        """Try to focus Terminal.app window/tab containing search term."""
        import subprocess

        # Sanitize search term to prevent AppleScript injection
        safe_search_term = TerminalFocuser._sanitize_applescript_string(search_term)

        # AppleScript to search Terminal.app windows by name
        script = f'''
        tell application "System Events"
            if not (exists process "Terminal") then
                return "not_running"
            end if
        end tell

        tell application "Terminal"
            repeat with w in windows
                set windowName to name of w
                if windowName contains "{safe_search_term}" then
                    set index of w to 1
                    activate
                    return "found"
                end if
            end repeat
            return "not_found"
        end tell
        '''

        try:
            result = subprocess.run(
                ['osascript', '-e', script],
                capture_output=True,
                text=True,
                timeout=5
            )
            output = result.stdout.strip()

            if output == "found":
                return {"success": True, "terminal": "Terminal.app", "project": search_term}
            elif output == "not_running":
                return {"success": False, "error": "Terminal.app not running"}
            else:
                return {"success": False, "error": "Not found in Terminal.app"}

        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Timeout searching Terminal.app"}
        except Exception as e:
            return {"success": False, "error": str(e)}


class RealtimeScanner:
    """Scans Claude session files for real-time monitoring."""

    # Sessions modified within this many seconds are considered active
    ACTIVE_THRESHOLD_SECONDS = 600  # 10 minutes
    # Sessions idle for this long are marked as idle
    IDLE_THRESHOLD_SECONDS = 300  # 5 minutes

    @staticmethod
    def scan_active_sessions() -> dict:
        """Scan all Claude sessions and return their current state."""
        result = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "active_sessions": [],
            "waiting_count": 0,
            "processing_count": 0,
            "projects_with_waiting": [],
        }

        if not CLAUDE_PROJECTS_DIR.exists():
            return result

        now = time.time()

        for proj_dir in CLAUDE_PROJECTS_DIR.iterdir():
            if not proj_dir.is_dir():
                continue

            # Extract project name from directory name
            # Format: -Users-username-path-to-project
            dir_name = proj_dir.name
            if dir_name.startswith("-"):
                parts = dir_name.split("-")
                project_name = parts[-1] if parts else dir_name
                # Try to reconstruct path
                project_path = "/" + "/".join(parts[1:]) if len(parts) > 1 else dir_name
            else:
                project_name = dir_name
                project_path = dir_name

            # Find session files (exclude agent- files)
            for session_file in proj_dir.glob("*.jsonl"):
                if session_file.name.startswith("agent-"):
                    continue

                mtime = session_file.stat().st_mtime
                age_seconds = now - mtime

                # Skip old sessions
                if age_seconds > RealtimeScanner.ACTIVE_THRESHOLD_SECONDS:
                    continue

                session_info = RealtimeScanner._parse_session(
                    session_file, project_name, project_path, age_seconds
                )

                if session_info:
                    result["active_sessions"].append(session_info)

                    if session_info["state"] in ("waiting_for_question", "waiting_for_approval"):
                        result["waiting_count"] += 1
                        if project_name not in result["projects_with_waiting"]:
                            result["projects_with_waiting"].append(project_name)
                    elif session_info["state"] == "processing":
                        result["processing_count"] += 1
                    # task_complete is not counted as waiting (no alert needed)

        # Sort by last activity (most recent first), handle None values
        result["active_sessions"].sort(
            key=lambda x: x.get("last_activity") or "", reverse=True
        )

        return result

    @staticmethod
    def _parse_session(session_file: Path, project_name: str, project_path: str, age_seconds: float) -> dict | None:
        """Parse a session file and extract current state."""
        try:
            with open(session_file, "r") as f:
                lines = f.readlines()

            if not lines:
                return None

            # Parse last entry
            last_entry = json.loads(lines[-1].strip())
            entry_type = last_entry.get("type", "unknown")

            # Get session ID
            session_id = last_entry.get("sessionId", session_file.stem)

            # Determine state
            state = "unknown"
            pending_approval = None
            last_tool = None
            last_message_preview = ""

            if age_seconds > RealtimeScanner.IDLE_THRESHOLD_SECONDS:
                state = "idle"
            elif entry_type == "user":
                state = "processing"
            elif entry_type == "assistant":
                message = last_entry.get("message", {})
                content = message.get("content", [])

                # Check for tool_use (pending approval) or AskUserQuestion
                has_question = False
                for item in content:
                    if isinstance(item, dict):
                        if item.get("type") == "tool_use":
                            tool_name = item.get("name", "Unknown")
                            tool_input = item.get("input", {})

                            # AskUserQuestion is a special case - it's asking a question
                            if tool_name == "AskUserQuestion":
                                state = "waiting_for_question"
                                has_question = True
                                pending_approval = {
                                    "type": "question",
                                    "tool_name": tool_name,
                                    "description": str(tool_input.get("questions", []))[:100],
                                }
                            else:
                                state = "waiting_for_approval"
                                pending_approval = {
                                    "type": "tool_use",
                                    "tool_name": tool_name,
                                    "description": tool_input.get("description", tool_input.get("command", "")[:100]),
                                }
                            last_tool = {"name": tool_name, "timestamp": last_entry.get("timestamp")}
                            break
                        elif item.get("type") == "text":
                            text = item.get("text", "")
                            last_message_preview = text[:150] + "..." if len(text) > 150 else text
                            # Check if the text ends with a question (simple heuristic)
                            if text.strip().endswith("?"):
                                has_question = True

                if state == "unknown":
                    # If message contains question, mark as waiting_for_question
                    # Otherwise it's task_complete (waiting for next instruction)
                    state = "waiting_for_question" if has_question else "task_complete"

            # Get model info
            model = last_entry.get("message", {}).get("model", "unknown")

            # Look for last tool usage in recent entries (scan last 10)
            if not last_tool:
                for line in reversed(lines[-10:]):
                    try:
                        entry = json.loads(line.strip())
                        if entry.get("type") == "assistant":
                            for item in entry.get("message", {}).get("content", []):
                                if isinstance(item, dict) and item.get("type") == "tool_use":
                                    last_tool = {
                                        "name": item.get("name", "Unknown"),
                                        "timestamp": entry.get("timestamp"),
                                    }
                                    break
                        if last_tool:
                            break
                    except:
                        continue

            return {
                "session_id": session_id,
                "project_path": project_path,
                "project_name": project_name,
                "state": state,
                "last_activity": last_entry.get("timestamp"),
                "idle_seconds": int(age_seconds),
                "model": model,
                "last_tool": last_tool,
                "last_message_preview": last_message_preview,
                "pending_approval": pending_approval,
            }

        except Exception as e:
            # Log error but don't fail
            print(f"Error parsing session {session_file}: {e}")
            return None


class HistoryHandler(http.server.SimpleHTTPRequestHandler):
    """Handler that serves static files and handles API requests."""

    def do_POST(self):
        """Handle POST requests for API endpoints."""
        parsed_path = urlparse(self.path)

        if parsed_path.path == "/api/add-instruction":
            self.handle_add_instruction()
        elif parsed_path.path == "/api/focus-terminal":
            self.handle_focus_terminal()
        elif parsed_path.path == "/api/focus-terminal-by-index":
            self.handle_focus_terminal_by_index()
        elif parsed_path.path == "/api/focus-terminal-by-id":
            self.handle_focus_terminal_by_id()
        else:
            self.send_error(404, "Not Found")

    def handle_focus_terminal_by_index(self):
        """Focus terminal window by its index (deprecated - use by-id)."""
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")
            data = json.loads(body)

            window_index = data.get("window_index")

            if not window_index:
                self.send_json_response({"error": "No window_index specified"}, 400)
                return

            result = TerminalFocuser.focus_by_index(int(window_index))
            self.send_json_response(result, 200 if result.get("success") else 404)

        except json.JSONDecodeError:
            self.send_json_response({"error": "Invalid JSON"}, 400)
        except Exception as e:
            self.send_json_response({"error": str(e)}, 500)

    def handle_focus_terminal_by_id(self):
        """Focus terminal window by its stable ID."""
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")
            data = json.loads(body)

            window_id = data.get("window_id")

            if not window_id:
                self.send_json_response({"error": "No window_id specified"}, 400)
                return

            result = TerminalFocuser.focus_by_id(int(window_id))
            self.send_json_response(result, 200 if result.get("success") else 404)

        except json.JSONDecodeError:
            self.send_json_response({"error": "Invalid JSON"}, 400)
        except Exception as e:
            self.send_json_response({"error": str(e)}, 500)

    def handle_focus_terminal(self):
        """Focus terminal window containing the specified project."""
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")
            data = json.loads(body)

            project_name = data.get("project_name", "")
            project_path = data.get("project_path", "")

            if not project_name and not project_path:
                self.send_json_response({"error": "No project specified"}, 400)
                return

            # Search term - use project name or last part of path
            search_term = project_name or project_path.split("/")[-1]

            result = TerminalFocuser.focus_terminal(search_term)
            self.send_json_response(result, 200 if result.get("success") else 404)

        except json.JSONDecodeError:
            self.send_json_response({"error": "Invalid JSON"}, 400)
        except Exception as e:
            self.send_json_response({"error": str(e)}, 500)

    def handle_add_instruction(self):
        """Add an instruction to CLAUDE.md."""
        try:
            # Read the request body
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")
            data = json.loads(body)

            instruction = data.get("instruction", "").strip()
            title = data.get("title", "").strip()

            if not instruction:
                self.send_json_response({"error": "No instruction provided"}, 400)
                return

            # Ensure .claude directory exists
            CLAUDE_MD_PATH.parent.mkdir(parents=True, exist_ok=True)

            # Read existing content
            existing_content = ""
            if CLAUDE_MD_PATH.exists():
                existing_content = CLAUDE_MD_PATH.read_text()

            # Check if instruction already exists
            if instruction in existing_content:
                self.send_json_response({
                    "success": False,
                    "message": "This instruction already exists in CLAUDE.md"
                }, 200)
                return

            # Append the new instruction
            timestamp = datetime.now().strftime("%Y-%m-%d")
            new_entry = f"\n\n## {title}\n*Added {timestamp} via Claude History Analyzer*\n\n{instruction}\n"

            with open(CLAUDE_MD_PATH, "a") as f:
                f.write(new_entry)

            self.send_json_response({
                "success": True,
                "message": f"Instruction added to {CLAUDE_MD_PATH}",
                "path": str(CLAUDE_MD_PATH)
            }, 200)

        except json.JSONDecodeError:
            self.send_json_response({"error": "Invalid JSON"}, 400)
        except Exception as e:
            self.send_json_response({"error": str(e)}, 500)

    def do_GET(self):
        """Handle GET requests - serve static files or API endpoints."""
        parsed_path = urlparse(self.path)

        if parsed_path.path == "/api/claude-md":
            self.handle_get_claude_md()
        elif parsed_path.path == "/api/realtime":
            self.handle_get_realtime()
        elif parsed_path.path == "/api/terminal-windows":
            self.handle_get_terminal_windows()
        else:
            # Serve static files
            super().do_GET()

    def handle_get_terminal_windows(self):
        """Return list of all Terminal windows."""
        try:
            windows = TerminalFocuser.list_terminal_windows()
            self.send_json_response({
                "windows": windows,
                "count": len(windows),
                "claude_count": sum(1 for w in windows if w.get("is_claude"))
            }, 200)
        except Exception as e:
            self.send_json_response({"error": str(e)}, 500)

    def handle_get_realtime(self):
        """Return real-time session monitoring data."""
        try:
            data = RealtimeScanner.scan_active_sessions()
            self.send_json_response(data, 200)
        except Exception as e:
            self.send_json_response({"error": str(e)}, 500)

    def handle_get_claude_md(self):
        """Return current CLAUDE.md content."""
        try:
            content = ""
            if CLAUDE_MD_PATH.exists():
                content = CLAUDE_MD_PATH.read_text()

            self.send_json_response({
                "exists": CLAUDE_MD_PATH.exists(),
                "path": str(CLAUDE_MD_PATH),
                "content": content
            }, 200)
        except Exception as e:
            self.send_json_response({"error": str(e)}, 500)

    def _get_cors_origin(self) -> str:
        """Get the allowed CORS origin (localhost only for security)."""
        return f"http://localhost:{PORT}"

    def send_json_response(self, data: dict, status_code: int = 200):
        """Send a JSON response."""
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", self._get_cors_origin())
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))

    def do_OPTIONS(self):
        """Handle CORS preflight requests."""
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", self._get_cors_origin())
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def log_message(self, format, *args):
        """Custom log format."""
        print(f"[{self.log_date_time_string()}] {args[0]}")


def main():
    """Start the server."""
    # Change to script directory
    os.chdir(Path(__file__).parent)

    # Allow port reuse to avoid "Address already in use" errors
    socketserver.TCPServer.allow_reuse_address = True

    with socketserver.TCPServer(("", PORT), HistoryHandler) as httpd:
        print(f"Claude History Server running at http://localhost:{PORT}")
        print(f"CLAUDE.md path: {CLAUDE_MD_PATH}")
        print("Press Ctrl+C to stop")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down...")


if __name__ == "__main__":
    main()
