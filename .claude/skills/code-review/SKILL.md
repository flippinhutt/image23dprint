---
name: code-review
description: Focused code review for image23dprint image processing and mesh logic.
---

## Scope
Reviews PRs and code changes for:
- Image processing efficiency (OpenCV).
- Mesh validity (manifoldness, orientation).
- Type hints and PEP 8 compliance.

## Process
1. Analyze the logic for potential off-by-one errors in heightmap mapping.
2. Check for memory-heavy operations on large images.
3. Validate that mesh generation handles edge cases (e.g., all-black images).

## Output Format
Markdown report with "Findings" and "Suggested Changes".
