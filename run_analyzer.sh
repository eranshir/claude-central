#!/bin/bash
# Claude History Analyzer - Crontab Runner
#
# Add to crontab with: crontab -e
# Example (run daily at 9 PM):
#   0 21 * * * /path/to/claude-central/run_analyzer.sh
#

# Change to script directory
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Load API key from .env file
if [ -f "$SCRIPT_DIR/.env" ]; then
    export $(grep -v '^#' "$SCRIPT_DIR/.env" | xargs)
fi

# Log file for cron output
LOG_FILE="$SCRIPT_DIR/analyzer.log"

# Run the analyzer
echo "=== Claude History Analyzer ===" >> "$LOG_FILE"
echo "Started at: $(date)" >> "$LOG_FILE"

# Use the project's virtual environment
PYTHON="$SCRIPT_DIR/venv/bin/python3"
"$PYTHON" "$SCRIPT_DIR/claude_history_analyzer.py" --output "$SCRIPT_DIR/history_data.json" 2>&1 | tee -a "$LOG_FILE"

echo "Finished at: $(date)" >> "$LOG_FILE"
echo "" >> "$LOG_FILE"
