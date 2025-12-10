#!/bin/bash
# Claude History Analyzer - Crontab Runner
#
# Add to crontab with: crontab -e
# Example (run daily at 9 PM):
#   0 21 * * * /Users/eranshir/Documents/Projects/claudeHistory/run_analyzer.sh
#
# Make sure to set ANTHROPIC_API_KEY in the script or in your environment

# Load environment (adjust path if needed)
if [ -f ~/.zshrc ]; then
    source ~/.zshrc
fi

# Or set the API key directly (uncomment and add your key):
# export ANTHROPIC_API_KEY="your-api-key-here"

# Change to script directory
cd "$(dirname "$0")"

# Log file for cron output
LOG_FILE="$(dirname "$0")/analyzer.log"

# Run the analyzer
echo "=== Claude History Analyzer ===" >> "$LOG_FILE"
echo "Started at: $(date)" >> "$LOG_FILE"

python3 claude_history_analyzer.py --output history_data.json 2>&1 | tee -a "$LOG_FILE"

echo "Finished at: $(date)" >> "$LOG_FILE"
echo "" >> "$LOG_FILE"
