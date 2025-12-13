# Claude Central

> *"Wait, which project was I working on? And did that agent ever finish the refactor?"* — You, probably

![Claude](https://img.shields.io/badge/Powered%20by-Claude%20Opus%204.5-blueviolet)
![Vibe](https://img.shields.io/badge/Vibe-Maximum-ff69b4)
![Projects](https://img.shields.io/badge/Projects-Too%20Many-orange)
![ADHD](https://img.shields.io/badge/ADHD-Friendly-brightgreen)
![Beads](https://img.shields.io/badge/Beads-Integrated-yellow)
![Live](https://img.shields.io/badge/Live-Monitoring-red)

## The Problem

It's 2 AM. You have **7 projects open**. You've spun up **3 agents** — one is refactoring your auth system, another is building a new feature, and the third one... wait, what was the third one doing? Something about tests? Or was that yesterday?

You're a **vibe coder**. You don't do linear. You do *parallel*. You context-switch like a caffeinated hummingbird. One moment you're deep in your iOS app, the next you're fixing a bug in your web dashboard, and somehow you ended up redesigning your database schema in a completely different project.

This is the way. This is the *vibe*.

But then comes **The Question™**: *"What have you actually accomplished this week?"*

You freeze. You have mass-produced more code than an LLM factory. But you couldn't tell anyone what. It's all a beautiful blur of:

- *"Let's spin up two agents for this"*
- *"Actually, let's also tackle that other thing"*
- *"Oh wait, I should check on that project from Tuesday"*
- *"New idea! Let me just quickly..."*

**Your brain is a chaos engine. This tool is your flight recorder.**

## The Solution

This tool digs through your Claude Code history across **ALL your projects** and reconstructs what you actually did. It's like having a second brain that actually remembers things — organized by project, by day, by session.

Finally, you can answer: *"What was I working on in that recipe app last Thursday?"* without scrolling through 47 conversation threads.

### Features

- **Multi-Project Dashboard** — See all your projects in one place, sorted by activity
- **Session Timeline** — Every coding session, every project, every day
- **AI-Powered Summaries** — Claude Opus 4.5 turns your chaotic sessions into coherent bullet points
- **Expandable Messages** — Click to see exactly what you asked (and what rabbit holes you went down)
- **GitHub Commit Links** — Connect your sessions to actual commits (proof you shipped something!)
- **Tag Support** — Links to releases when available, because you're professional like that
- **[Beads](https://github.com/steveyegge/beads) Integration** — See all your agent issues in one place, filterable by status and type
- **CLAUDE.md Suggestions** — AI-generated instructions based on your coding patterns, one-click save to CLAUDE.md
- **Search Everything** — Find that one session where you "fixed the auth thing" across all projects
- **Date Filtering** — What did I do last week? Last month? Before my mass-deletion spree?
- **Cron-Ready** — Runs daily in the background. Set it and forget it. (You will forget it. That's the point.)

### Live Monitoring (New in v0.0.2!)

- **Real-Time Session Tracking** — See all active Claude sessions across every project, updated every 3 seconds
- **Smart State Detection** — Know when Claude needs approval, is asking a question, is processing, or has completed a task
- **Configurable Alerts** — Sound notifications when any session waits too long for input (configurable delay, default 20s)
- **Browser Notifications** — Get notified even when the tab is in the background
- **Terminal Window Control** — Jump to any project's terminal with one click (macOS only, works with full-screen/Spaces)
- **Per-Project Window List** — See all terminal windows grouped by project for easy navigation

## Perfect For

- 🧠 **ADHD Coders** — External memory for when your internal memory said "nah"
- 🐙 **Multi-Project Jugglers** — Track progress across your entire portfolio of half-finished side projects
- 🤖 **Agent Wranglers** — Remember what you told your agents to do (and whether they did it)
- 🌀 **Context Switchers** — Pick up exactly where you left off, even if "where you left off" was 5 projects ago
- 📝 **Accountability Seekers** — Prove to yourself (and others) that you're actually productive

## Screenshots

Your command center for multi-project chaos:

```
┌─────────────────────────────────────────────────────────────────┐
│  Claude Code History                    [Search...] [Date ▼]   │
├─────────────────────────────────────────────────────────────────┤
│  📊 12 Projects  │  47 Active Days  │  156 Sessions  │  89 🏷️  │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌───────────────────────────────────────────┐│
│  │ PROJECTS     │  │ pet-tracker                     [GitHub] ││
│  │──────────────│  │───────────────────────────────────────────││
│  │ pet-tracker47│  │ December 10, 2025                        ││
│  │ budgetapp 32 │  │ ┌───────────────────────────────────────┐ ││
│  │ ml-pipeline18│  │ │ 09:13 - 15:35       [18 msgs] [🏷️ v2.1]│ ││
│  │ website   12 │  │ │ Spun up 2 agents:                     │ ││
│  │ cli-tool   8 │  │ │ • Agent 1: Push notification system   │ ││
│  │ api-proxy  5 │  │ │ • Agent 2: Pet activity dashboard     │ ││
│  │ dotfiles   3 │  │ │ Merged both, deployed to staging      │ ││
│  │ ...          │  │ └───────────────────────────────────────┘ ││
│  └──────────────┘  │                                           ││
│                    │ December 9, 2025                          ││
│                    │ ┌───────────────────────────────────────┐ ││
│                    │ │ 22:47 - 02:15       [43 msgs] [2 🏷️]  │ ││
│                    │ │ • Auth system rewrite (the big one)   │ ││
│                    │ │ • "Quick" database migration          │ ││
│                    │ │ • Definitely went to bed at a         │ ││
│                    │ │   reasonable hour                     │ ││
│                    │ └───────────────────────────────────────┘ ││
│                    └───────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
```

## Installation

### Prerequisites

- Python 3.9+
- Claude Code (with some history to analyze)
- An Anthropic API key (optional, for enhanced summaries)
- Multiple projects in various states of completion (mandatory for true vibe coders)

### Quick Start

```bash
# Clone the repo
git clone https://github.com/eranshir/claude-central.git
cd claude-central

# Install dependencies
pip install anthropic

# Set up your API key (optional but recommended)
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY

# Run the analyzer
python3 claude_history_analyzer.py

# Start the server (includes API for saving suggestions)
python3 server.py
# Then open http://localhost:9347
```

## Usage

### Basic Commands

```bash
# Full analysis with AI summaries
python3 claude_history_analyzer.py

# Quick analysis without API calls (uses built-in summaries)
python3 claude_history_analyzer.py --no-api

# Force refresh everything (when you need a fresh start)
python3 claude_history_analyzer.py --force-refresh

# Custom output location
python3 claude_history_analyzer.py --output ~/my-history.json
```

### Daily Auto-Updates (Set It and Forget It)

Because you *will* forget to run this manually:

```bash
# Edit crontab
crontab -e

# Add this line (runs daily at 9 PM)
0 21 * * * /path/to/claude-central/run_analyzer.sh
```

Now your history updates itself while you're busy starting another project.

### CLAUDE.md Suggestions

The analyzer can generate personalized instructions for your `~/.claude/CLAUDE.md` file based on:
- **Your coding patterns** — Common requests, repeated tasks, tools you use
- **Best practices** — Tailored to the types of projects you're building (iOS, web, ML, etc.)

```bash
# Generate suggestions (requires API key)
python3 claude_history_analyzer.py

# Or regenerate suggestions from existing data
python3 generate_suggestions.py

# Start server to enable one-click saving
python3 server.py
```

Then click the **Suggestions** tab in the UI to see your personalized recommendations. Each suggestion shows:
- The instruction text (what gets added to CLAUDE.md)
- A rationale explaining why it would help
- An **"Add to CLAUDE.md"** button for instant saving

## How It Works

```
~/.claude/
├── history.jsonl          ← Your prompts across ALL projects
└── projects/
    ├── project-a/
    │   └── session-123.jsonl   ← Full conversation history
    ├── project-b/
    │   └── session-456.jsonl
    └── ...
```

The analyzer:
1. **Scans** your entire Claude Code history
2. **Groups** by project and date
3. **Extracts** summaries (Claude already summarizes your sessions!)
4. **Enhances** with AI-generated daily overviews
5. **Links** git commits within session timeframes
6. **Discovers** [Beads](https://github.com/steveyegge/beads) issues in your projects
7. **Renders** everything in a searchable web UI

### Live Monitor

The Live Monitor provides real-time observability across all your active Claude sessions:

```
┌─────────────────────────────────────────────────────────────────┐
│ 🔴 LIVE MONITOR                                    [Settings]   │
├─────────────────────────────────────────────────────────────────┤
│  Waiting: 1  │  Processing: 2  │  Ready: 1  │  Idle: 3          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│ ⚡ pet-tracker (Needs Approval · 25s ago)          [Jump]       │
│   └─ Tool: Bash · Model: opus-4.5 · "Running npm install..."   │
│                                                                 │
│ 🔄 budgetapp (Processing · 3s ago)                 [Jump]       │
│   └─ Tool: Edit · Model: opus-4.5 · Agent responding           │
│                                                                 │
│ ✅ ml-pipeline (Ready · 45s ago)                   [Jump]       │
│   └─ Task complete · Waiting for next instruction              │
│                                                                 │
│ 💤 website (Idle · 12m ago)                        [Jump]       │
│   └─ Last: Read · Session inactive                             │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**States:**
- **Needs Approval** (orange) — Claude is waiting for tool approval (Bash, Write, etc.)
- **Question** (orange) — Claude asked you a question
- **Processing** (blue) — Claude is actively working
- **Ready** (green) — Task complete, waiting for your next instruction
- **Idle** (gray) — No activity for 5+ minutes

**Alert Settings:**
- Configurable waiting delay (default 20 seconds) — only alert after waiting this long
- Sound notifications with volume control
- Browser notifications (works in background tabs)
- Visual indicators in the UI

**Terminal Window Control (macOS only):**
- Click "Jump" to instantly focus that project's terminal window
- Works even with full-screen windows across different macOS Spaces
- Shows all terminal windows grouped by project
- *Note: Terminal control uses AppleScript and is currently macOS-only*

## Configuration

| Option | Description |
|--------|-------------|
| `--output`, `-o` | Where to save the JSON (default: `history_data.json`) |
| `--force-refresh`, `-f` | Regenerate everything from scratch |
| `--no-api` | Skip AI summaries (faster, free, slightly less pretty) |

## Privacy

- **100% Local** — Your history stays on your machine
- **API calls only to Anthropic** — And only for generating summaries
- **Secrets are gitignored** — `.env` and `history_data.json` never leave your machine
- **No telemetry** — We respect the chaos. We don't track it.

## FAQ

**Q: I have like 20 projects. Will this slow down?**
A: The analyzer is incremental — it only processes new sessions. First run might take a minute, subsequent runs are fast.

**Q: Some summaries look weird?**
A: Sessions without built-in Claude summaries get a fallback. Use the API key for better results.

**Q: Can I see what my agents did?**
A: Yes! Agent sessions are captured just like regular sessions. You'll finally know if that background refactor actually finished.

**Q: What's the Beads integration?**
A: If you use [Beads](https://github.com/steveyegge/beads) (the AI-friendly issue tracker), this tool automatically discovers and displays all your Beads issues per project. Filter by open/closed, bug/feature/task, and see close reasons for resolved issues. Perfect for tracking what your agents have been working on.

**Q: How do CLAUDE.md suggestions work?**
A: When you run the analyzer with an API key, Claude analyzes your coding patterns across all projects and generates personalized instructions for your CLAUDE.md file. Click "Suggestions" tab, then "Add to CLAUDE.md" to save any suggestion. Suggestions include coding style preferences, best practices for your project types, and patterns it noticed in your work.

**Q: What's the Live Monitor?**
A: The Live tab shows real-time status of all your active Claude sessions. It detects when Claude needs approval, is asking a question, is processing, or has finished a task. You can configure alerts to sound after a session has been waiting for your input for a certain time (default 20 seconds).

**Q: Why don't I get alerts immediately when Claude finishes?**
A: By design! The "waiting delay" setting (default 20s) prevents alert spam. You only get notified if Claude has been waiting for approval or asking a question for longer than this threshold. When Claude completes a task and is just "Ready" for your next instruction, no alert fires — that's intentional.

**Q: How does the "Jump to Terminal" feature work?**
A: On macOS, clicking the Jump button uses AppleScript to focus the Terminal window for that project. It even works with full-screen windows across different Spaces — it uses the Terminal Window menu to switch, which bypasses the usual Space restrictions. This feature is currently macOS-only; on other platforms the Jump buttons won't appear.

**Q: I accidentally mass-deleted my ~/.claude folder. Can this help?**
A: No. This tool reads history, it doesn't create it. I'm sorry for your loss. 🕯️

**Q: Is this official Anthropic software?**
A: Nope! Just a tool built by a fellow vibe coder who kept losing track of their 15 concurrent projects.

## Contributing

PRs welcome! Especially if you:
- Have ideas for better multi-agent tracking
- Want to add project tagging/categorization
- Can make the UI even more ADHD-friendly
- Just want to vibe

## License

MIT — Fork it, modify it, ship it. Just keep vibing.

---

*Built during a mass-coding session across 4 projects, documented by the very tool it describes, for coders who understand that "focus" is just one approach to productivity.*

🧠 **Your external memory awaits.**

🤖 **Happy Vibe Coding!**
