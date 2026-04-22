# Quick JSON Reader
## cli | ai tool integration | logging | data viewing and inspection

TRY IT HERE!  [randyhaylor.github.io/jsonreader/](https://randyhaylor.github.io/jsonreader/)

> Fast JSON search tool with compact outputs for AI, logging, and application workflows—portable and easy to extend.

## Mission

Provide a simple, powerful, and deterministic tool for humans and AI agents to quickly and efficiently view JSON content.

This tool is designed to make large or complex JSON data immediately understandable, while supporting both full inspection and precise extraction without forcing data loss.

## Implementations

This project serves as a foundational engine for multiple use cases:

- JSON reader web modules
- AI agent tooling
- Logging and data automation

## Overview

Quick JSON Reader renders JSON as a clean, indentation-based tree instead of raw JSON formatting.

It acts as a projection layer over JSON:
- Non-destructive by default
- Selectively reductive when explicitly instructed

## Runtime Environments

Quick JSON Reader uses a single JavaScript engine in:

- Node.js for CLI and AI-agent execution
- Browser JavaScript for a static web app

The behavior is intended to remain consistent across environments.

## Features

### Rendering
- Indentation-based tree view
- Line numbers for text output by default
- Optional truncation for text and CSV

### Search
- `--search-keys`
- `--search-vals`
- `--include-search-children`

### Field Exclusion
- `--exclude-fields-matching`
- `--exclude-fields-containing`

### Output Modes
- `txt` (default)
- `csv` (RFC-compliant)
- `json` (machine-safe)

### Schema
- `--show-schema` (standalone only)
- Lightweight inferred structure/type projection
- Not a formal JSON Schema generator

### Stats
- `--show-stats` prepends totals (char count, nesting depth, objects, arrays, json-valid) to the output
- In `--output json` mode the stats are injected as a top-level `jsonStats` object so the result stays valid JSON

## CLI Usage

```bash
node quick_json_reader.js input.json
```

### CLI Examples

All examples below use `examples/sample_easy_json_reader_input.json` as input.

<table>
<tr>
<td>

**Default (txt)**

```bash
node src/quick_json_reader.js \
  examples/sample_easy_json_reader_input.json
```

```
 1 | user
 2 |   name: alice
 3 |   token: abc123
 4 |   profile
 5 |     bio: loves synths, math, and "quotes"
 6 |     secretNote: deep hidden note
 7 |   events
 8 |     [0]
 9 |       type: login
10 |       status: ok
11 |     [1]
12 |       type: purchase
13 |       status: failed
14 | system
15 |   status: ok
16 |   long: The quick brown fox jumps over the lazy dog.
```

</td>
<td>

**Schema**

```bash
node src/quick_json_reader.js \
  examples/sample_easy_json_reader_input.json \
  --show-schema
```

```json
{
  "user": {
    "name": "string",
    "token": "string",
    "profile": {
      "bio": "string",
      "secretNote": "string"
    },
    "events": [
      {
        "type": "string",
        "status": "string"
      }
    ]
  },
  "system": {
    "status": "string",
    "long": "string"
  }
}
```

</td>
<td>

**Exclude fields**

```bash
node src/quick_json_reader.js \
  examples/sample_easy_json_reader_input.json \
  --exclude-fields-matching token secretNote
```

```
 1 | user
 2 |   name: alice
 3 |   profile
 4 |     bio: loves synths, math, and "quotes"
 5 |   events
 6 |     [0]
 7 |       type: login
 8 |       status: ok
 9 |     [1]
10 |       type: purchase
11 |       status: failed
12 | system
13 |   status: ok
14 |   long: The quick brown fox jumps over the lazy dog.
```

</td>
</tr>
<tr>
<td>

**Search + include children**

```bash
node src/quick_json_reader.js \
  examples/sample_easy_json_reader_input.json \
  --search-vals failed --include-search-children
```

```
1 | user
2 |   events
3 |     [1]
4 |       status: failed
```

</td>
<td>

**Show stats**

```bash
node src/quick_json_reader.js \
  examples/sample_easy_json_reader_input.json \
  --show-stats
```

```
total char count: 386
nesting depth: 5
total objects: 6
total arrays: 1
json-valid: true
 1 | user
 2 |   name: alice
 3 |   token: abc123
 ...
```

</td>
<td>

**JSON output + search-keys**

```bash
node src/quick_json_reader.js \
  examples/sample_easy_json_reader_input.json \
  --output json --search-keys status
```

```json
{
  "user": {
    "events": [
      {
        "status": "ok"
      },
      {
        "status": "failed"
      }
    ]
  },
  "system": {
    "status": "ok"
  }
}
```

</td>
</tr>
</table>

## Browser Usage

Put these in the same folder:
- `quick_json_reader.js`
- `quick_json_reader_web.html`

Then open the HTML file in a browser.

The browser uses the same engine via:
- `QuickJsonReader.runWithJsonText(jsonText, config)`
- `QuickJsonReader.runWithValue(value, config)`

## Examples

```bash
node quick_json_reader.js input.json --search-vals error timeout
node quick_json_reader.js input.json --search-keys user profile
node quick_json_reader.js input.json --search-keys profile --include-search-children
node quick_json_reader.js input.json --exclude-fields-matching token password
node quick_json_reader.js input.json --output csv
node quick_json_reader.js input.json --output json
node quick_json_reader.js input.json --show-schema
node quick_json_reader.js input.json --show-stats
```

## Output Behavior

| Output | Line Numbers | Truncation | Notes |
|--------|-------------|------------|------|
| txt    | ON (default) | yes | human-readable |
| csv    | OFF (default) | yes | RFC-compliant |
| json   | never | no | machine-safe |

## Data Fidelity

- No data is removed unless explicitly requested
- Search narrows scope but preserves structure
- Exclude fully removes matching fields (and their subtrees) from the output
- JSON output remains usable for downstream tools

## Testing

```bash
node --test test_quick_json_reader.js
```

## Author

Randy Haylor
