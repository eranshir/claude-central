#!/usr/bin/env python3
"""Generate CLAUDE.md suggestions from existing history data."""

import json
import os
from pathlib import Path

# Load .env file
env_file = Path(__file__).parent / ".env"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ[key] = value

import anthropic
from claude_history_analyzer import generate_claude_md_suggestions

# Check API key
api_key = os.environ.get("ANTHROPIC_API_KEY")
if not api_key:
    print("Error: ANTHROPIC_API_KEY not found")
    exit(1)

print("API key: [configured]")

# Load existing data
data_file = Path(__file__).parent / "history_data.json"
data = json.load(open(data_file))
output_data = data.get("projects", {})
print(f"Projects: {len(output_data)}")

# Create client
client = anthropic.Anthropic(api_key=api_key)

# Generate suggestions
suggestions = generate_claude_md_suggestions(client, output_data)
print(f"Generated {len(suggestions)} suggestions")

if suggestions:
    # Save to JSON
    data["suggestions"] = suggestions
    with open(data_file, "w") as f:
        json.dump(data, f, indent=2)
    print(f"Saved suggestions to {data_file}")

    # Preview
    for i, s in enumerate(suggestions[:3], 1):
        print(f"\n{i}. {s.get('title')}")
        print(f"   {s.get('instruction', '')[:80]}...")
