---
name: learn
description: >-
  Use this skill to break down and explain code changes, architectural decisions,
  and repository modifications in clear, intuitive terms. Explains what files changed,
  what logic was introduced or removed, and how each change is practically useful
  to the user and system stability.
---

# Learn & Code Explain Skill

This skill guides the agent on how to explain technical changes, system refactorings, and architectural patterns to the user. It bridges the gap between code implementation and user comprehension, ensuring the user is never left wondering *"what did the agent just do and why does it matter?"*.

---

## When to Use

Activate this skill when:
- The user asks to understand code changes (e.g., *"explain the changes"*, *"what did you do?"*, *"how is this useful?"*).
- Substantial architectural refactoring or feature integration has just been completed.
- Teaching the user how a subsystem works under the hood (e.g., multi-process logging, NAS sync, audio metadata tagging).

---

## The 3-Part Explanation Framework

Every explanation delivered under this skill must follow the **3-Part Framework**:

### 1. The Big Picture (Problem vs. Solution)
- **The Problem**: What was clunky, broken, missing, or inefficient before?
- **The Solution**: What core architectural change was introduced to solve it?

### 2. File-by-File Breakdown
For each modified, created, or deleted file, present:
- **File**: Relative path link
- **What Changed**: Concise summary of what code was added, modified, or removed
- **How It's Useful**: Tangible benefit to the user (e.g., *“prevents crash when running both bot and web app on Windows”*, *“cuts log files from 6 down to 2 readable files”*, *“makes song titles clean without manual editing”*)

### 3. Visual Flow or Before/After Comparison
Use Mermaid diagrams, comparison tables, or code side-by-sides to make complex mechanics instantly intuitive.

---

## Explanation Guidelines
- **Avoid dry diff dumps**: Don't just paste code diffs without context. Explain the *intent* behind the code.
- **Highlight practical user impact**: Focus on what changes for the user's workflow (e.g., terminal output, file locations, error detection).
- **Proactive transparency**: If a file was deleted or a dependency changed, explain why it was safe to remove.
