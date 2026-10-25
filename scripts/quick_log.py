#!/usr/bin/env python3
"""
Quick Log Utility
Appends ideas or fixes to docs/ideas.md or docs/fixes.md with timestamps.
Used by VS Code tasks, CLI shortcuts, and slash commands.
"""

import argparse
import datetime
import os
import sys

def main():
    parser = argparse.ArgumentParser(description="Quick logger for ideas and fixes")
    parser.add_argument("--type", choices=["idea", "fix"], required=True, help="Entry type: idea or fix")
    parser.add_argument("message", nargs="+", help="Content of the idea or fix")

    args = parser.parse_args()
    text = " ".join(args.message).strip()

    if not text:
        print("Error: empty message", file=sys.stderr)
        sys.exit(1)

    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    docs_dir = os.path.join(repo_root, "docs")
    os.makedirs(docs_dir, exist_ok=True)

    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    if args.type == "idea":
        target_file = os.path.join(docs_dir, "ideas.md")
        entry = f"- [{timestamp}] {text}\n"
    else:
        target_file = os.path.join(docs_dir, "fixes.md")
        entry = f"- [ ] [{timestamp}] {text}\n"

    with open(target_file, "a", encoding="utf-8") as f:
        f.write(entry)

    print(f"✓ Logged {args.type} to {os.path.relpath(target_file, repo_root)}")

if __name__ == "__main__":
    main()
