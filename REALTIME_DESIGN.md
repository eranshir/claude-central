# Realtime Monitoring Feature Design

## Overview

Add a realtime monitoring component to the Claude History Analyzer that provides:
1. Live observability on all active Claude sessions across projects
2. Alerting when any session is waiting for human input
3. Configurable notification mechanisms (sound, browser notifications, visual)

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Frontend (index.html)                        │
├─────────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────────────────┐ │
│  │ Live Monitor │  │ Alert Panel  │  │    Notification Manager    │ │
│  │   Component  │  │  (Waiting)   │  │  - Sound alerts            │ │
│  │              │  │              │  │  - Browser notifications   │ │
│  │ • Sessions   │  │ • Count      │  │  - Visual pulse            │ │
│  │ • Tools      │  │ • Projects   │  │  - Settings persistence    │ │
│  │ • Status     │  │ • Actions    │  │                            │ │
│  └──────────────┘  └──────────────┘  └────────────────────────────┘ │
│                              ▲                                       │
│                              │ Poll every 2-5 seconds               │
│                              │                                       │
└──────────────────────────────┼───────────────────────────────────────┘
                               │
                    ┌──────────┴──────────┐
                    │  GET /api/realtime   │
                    └──────────┬──────────┘
                               │
┌──────────────────────────────┼───────────────────────────────────────┐
│                         server.py                                    │
├──────────────────────────────┼───────────────────────────────────────┤
│                    ┌─────────┴─────────┐                             │
│                    │  RealtimeScanner  │                             │
│                    │                   │                             │
│                    │ • Scan sessions   │                             │
│                    │ • Parse states    │                             │
│                    │ • Extract tools   │                             │
│                    │ • Check beads     │                             │
│                    └─────────┬─────────┘                             │
│                              │                                       │
└──────────────────────────────┼───────────────────────────────────────┘
                               │
              ┌────────────────┼────────────────┐
              │                │                │
              ▼                ▼                ▼
    ~/.claude/projects/   ~/.claude/history.jsonl   .beads/issues.jsonl
         *.jsonl                                    (per project)
```

## API Design

### GET /api/realtime

Returns current state of all active Claude sessions.

**Response:**
```json
{
  "timestamp": "2025-12-13T07:30:00Z",
  "active_sessions": [
    {
      "session_id": "7e1472f7-7fa5-40cd-b4d4-221cf2adb3e4",
      "project_path": "/Users/eranshir/Documents/Projects/claudeHistory",
      "project_name": "claudeHistory",
      "state": "waiting_for_input",  // or "processing", "idle"
      "last_activity": "2025-12-13T07:29:55Z",
      "idle_seconds": 5,
      "current_agent": {
        "type": "main",  // or "subagent"
        "model": "claude-opus-4-5-20251101"
      },
      "last_tool": {
        "name": "Bash",
        "timestamp": "2025-12-13T07:29:50Z"
      },
      "last_message_preview": "Analyzing session states...",
      "pending_approval": {
        "type": "tool_use",  // or "question", null
        "tool_name": "Bash",
        "description": "Run npm install"
      }
    }
  ],
  "waiting_count": 1,
  "processing_count": 0,
  "projects_with_waiting": ["claudeHistory"],
  "beads_in_progress": [
    {
      "project": "claudeHistory",
      "issue_id": "123",
      "title": "Add realtime monitoring",
      "type": "feature"
    }
  ]
}
```

## Session State Detection Logic

```python
def detect_session_state(session_file):
    """
    Determine session state from last entries.

    States:
    - waiting_for_input: Last entry is assistant, waiting for user
    - waiting_for_approval: Last entry is assistant with tool_use, needs approval
    - processing: Last entry is user (Claude is responding)
    - idle: No activity for > 5 minutes
    """
    with open(session_file) as f:
        lines = f.readlines()

    if not lines:
        return "idle"

    last_entry = json.loads(lines[-1])
    entry_type = last_entry.get('type')

    # Check file modification time for idle detection
    mtime = os.path.getmtime(session_file)
    age_seconds = time.time() - mtime

    if age_seconds > 300:  # 5 minutes
        return "idle"

    if entry_type == "user":
        return "processing"

    if entry_type == "assistant":
        # Check if waiting for tool approval
        content = last_entry.get('message', {}).get('content', [])
        for item in content:
            if item.get('type') == 'tool_use':
                return "waiting_for_approval"
        return "waiting_for_input"

    return "unknown"
```

## Frontend Components

### 1. Live Monitor Panel

A collapsible panel showing real-time activity:

```
┌─────────────────────────────────────────────────────────┐
│ 🔴 LIVE MONITOR                          [Settings] [▼] │
├─────────────────────────────────────────────────────────┤
│                                                         │
│ ⚡ claudeHistory (waiting 5s)                           │
│   └─ Tool: Read · Model: opus-4.5 · "Analyzing..."     │
│                                                         │
│ 🔄 foodis (processing)                                  │
│   └─ Tool: Edit · Model: opus-4.5 · Agent responding   │
│                                                         │
│ 💤 guitarHub (idle 12m)                                 │
│   └─ Last: Bash · Session ended                        │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### 2. Alert Banner

Appears when any session needs attention:

```
┌─────────────────────────────────────────────────────────┐
│ 🔔 1 session waiting for input                    [×]   │
│    claudeHistory - Tool approval needed (Bash)          │
│    [Open Terminal] [Dismiss]                            │
└─────────────────────────────────────────────────────────┘
```

### 3. Notification Settings Modal

```
┌─────────────────────────────────────────────────────────┐
│ Notification Settings                             [×]   │
├─────────────────────────────────────────────────────────┤
│                                                         │
│ ☑ Enable notifications                                  │
│                                                         │
│ Alert when session is waiting for:                      │
│   ☑ Tool approval (Bash, Write, etc.)                  │
│   ☑ User response to question                          │
│   ☐ Any input (includes typing responses)              │
│                                                         │
│ Notification methods:                                   │
│   ☑ Sound alert                                        │
│      Volume: [━━━━━━━━━●━] 80%                         │
│      Sound: [Chime ▼]                                   │
│   ☑ Browser notification                               │
│   ☑ Visual pulse (red dot)                             │
│                                                         │
│ Timing:                                                 │
│   Poll interval: [3] seconds                           │
│   Alert cooldown: [30] seconds (prevent spam)          │
│                                                         │
│ [Test Alert]                        [Save] [Cancel]     │
└─────────────────────────────────────────────────────────┘
```

## Sound Assets

Create simple alert sounds (can be base64-encoded in JS):
- `alert-chime.mp3` - Pleasant chime for attention
- `alert-ding.mp3` - Short ding
- `alert-bell.mp3` - Bell sound

Or use Web Audio API to generate tones programmatically (no external files).

## Implementation Plan

### Phase 1: Backend API (server.py)
1. Add `GET /api/realtime` endpoint
2. Implement `RealtimeScanner` class:
   - Scan `~/.claude/projects/` for recent sessions
   - Parse session state from last entries
   - Extract tool usage, model info
   - Check for pending approvals
3. Include beads in-progress items

### Phase 2: Frontend - Live Monitor
1. Add Live Monitor panel to UI
2. Implement polling mechanism (2-5 second interval)
3. Display session states with visual indicators
4. Show tool usage and message previews

### Phase 3: Notification System
1. Add notification settings modal
2. Implement sound alerts (Web Audio API)
3. Add browser notification support (with permission request)
4. Visual pulse indicator (favicon + UI element)
5. Persist settings to localStorage

### Phase 4: Polish
1. Cooldown logic to prevent alert spam
2. "Snooze" functionality
3. Quick actions (open terminal to project)
4. Keyboard shortcuts

## Data Flow

```
1. Browser polls /api/realtime every N seconds
2. Server scans ~/.claude/projects/* for .jsonl files
3. For each file modified in last 10 minutes:
   - Parse last entry
   - Determine state
   - Extract metadata
4. Return aggregated state
5. Frontend compares with previous state
6. If new "waiting" session detected:
   - Check notification settings
   - Play sound if enabled
   - Show browser notification if enabled
   - Update visual indicators
```

## File Changes Required

1. `server.py` - Add /api/realtime endpoint and RealtimeScanner
2. `index.html` - Add Live Monitor panel, notifications, settings modal
3. (Optional) `realtime.py` - Separate module for scanning logic

## Open Questions

1. Should we use WebSocket instead of polling for lower latency?
   - Polling is simpler, WebSocket requires more infrastructure
   - 2-3 second polling is probably sufficient for this use case

2. How to handle multiple browser tabs?
   - Use localStorage to coordinate notifications
   - Only one tab should play sounds

3. Should we add a system tray component?
   - Would require Electron or native app
   - Out of scope for initial version
