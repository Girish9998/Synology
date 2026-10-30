# Workspace Agent Guidelines

## Quick Logging (Ideas & Fixes)
When the user sends a message starting with `idea:`, `!idea`, `fix:`, or `!fix`:
1. Execute the quick log script:
   - For ideas: `python scripts/quick_log.py --type idea "<content>"`
   - For fixes: `python scripts/quick_log.py --type fix "<content>"`
2. Reply with a brief confirmation:
   `✓ Logged <type> to docs/<type>s.md: <content>`
3. Continue assisting with any prior context or tasks.
