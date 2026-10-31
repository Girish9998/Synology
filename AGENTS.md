# Workspace Agent Guidelines

## Code Explanations & Transparency (Learn Skill)
When bringing significant code changes or when requested by the user:
1. Break down the changes using the **3-Part Framework** defined in `.agents/skills/learn/SKILL.md`:
   - **The Big Picture**: Problem vs. Solution.
   - **File-by-File Breakdown**: What changed and specifically **how it is useful** to the user.
   - **Visual Flow**: Diagram or before/after comparison.
2. Focus on practical user impacts (performance, crash prevention, clean UI/logs, maintainability) rather than dry diffs.

## Quick Logging (Ideas & Fixes)
When the user sends a message starting with `idea:`, `!idea`, `fix:`, or `!fix`:
1. Execute the quick log script:
   - For ideas: `python scripts/quick_log.py --type idea "<content>"`
   - For fixes: `python scripts/quick_log.py --type fix "<content>"`
2. Reply with a brief confirmation:
   `✓ Logged <type> to docs/<type>s.md: <content>`
3. Continue assisting with any prior context or tasks.
