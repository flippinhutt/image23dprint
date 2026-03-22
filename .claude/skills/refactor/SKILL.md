---
name: refactor
description: Guidance for refactoring image23dprint modules.
---

## Scope
Simplifying the pipeline, extracting reusable mesh utilities, and optimizing the ingestion flow.

## Process
1. Identify tight coupling between image processing and mesh generation.
2. Propose abstract interfaces for different mesh exporters.
3. Ensure no regression in STL output quality.

## Output Format
Summary of refactoring goals followed by the `multi_replace_file_content` calls.
