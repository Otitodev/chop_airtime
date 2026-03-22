---
name: Use .venv virtual environment
description: Always activate .venv before running Python commands in the backend
type: feedback
---

Always use the `.venv` virtual environment when running Python commands in this project.

**Why:** The project dependencies (langchain_core, etc.) are installed in `.venv`, not globally.

**How to apply:** Prefix Python commands with `.venv/Scripts/python` (Windows) or source `.venv/bin/activate` before running anything in the backend directory.
