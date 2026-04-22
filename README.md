# Quick JSON Reader

> A simple, powerful, and deterministic tool for humans and AI agents to quickly and efficiently view JSON content.

---

## Mission

Provide a fast, reliable way to inspect, search, and understand JSON data without formatting noise or unnecessary complexity.

Quick JSON Reader enables both:
- full-fidelity inspection of JSON data
- precise extraction of relevant content when needed

---

## Implementations

This tool serves as a foundational engine for:

- JSON reader web modules
- AI agent tooling
- Logging and data automation

---

## Overview

Quick JSON Reader renders JSON as a clean, indentation-based tree instead of raw JSON formatting.

It acts as a projection layer over JSON:
- Non-destructive by default
- Selectively reductive when explicitly instructed

---

## Features

### Rendering
- Indentation-based tree view
- Line numbers (default for text)
- Optional truncation

### Search
- --search-keys
- --search-vals
- --include-search-children

### Field Suppression
- --hide-fields-matching
- --hide-fields-containing

### Output Modes
- txt (default)
- csv (RFC-compliant)
- json (machine-safe)

### Schema
- --show-schema (standalone only)
- Lightweight inferred structure

---

## Usage

python quick_json_reader.py input.json

---

## Testing

pytest test_quick_json_reader.py

---

## Author

Randy Haylor
