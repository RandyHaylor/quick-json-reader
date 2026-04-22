---
name: quick-json-reader
description: Deterministic JSON inspection and extraction tool for humans and AI agents.
tools:
  - python
  - cli
  - json
---

## Purpose

Inspect, search, and extract structured JSON data efficiently.

## Core Model

Parse → Search → Hide → Prune → Render

- Search determines relevance
- Hide determines visibility

## Patterns

Search values:
--search-vals error

Search keys:
--search-keys user profile

Expand:
--include-search-children

Hide:
--hide-fields-matching token

CSV:
--output csv

JSON:
--output json

Schema:
--show-schema

## Notes

- Non-destructive by default
- Filtering is explicit
