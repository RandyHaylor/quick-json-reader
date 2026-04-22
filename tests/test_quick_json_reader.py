import csv
import io
import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path('/mnt/data/easy_json_reader_by_randy_haylor.py')

FIXTURE = {
    "user": {
        "name": "alice",
        "token": "abc123",
        "profile": {
            "bio": "loves synths, math, and \"quotes\"",
            "secretNote": "deep hidden note"
        },
        "events": [
            {"type": "login", "status": "ok"},
            {"type": "purchase", "status": "failed"}
        ]
    },
    "system": {
        "status": "ok",
        "long": "X" * 40
    }
}


def run_cli(tmp_path, *args):
    src = tmp_path / 'sample.json'
    src.write_text(json.dumps(FIXTURE), encoding='utf-8')
    cmd = [sys.executable, str(SCRIPT), str(src), *args]
    return subprocess.run(cmd, capture_output=True, text=True)


def test_default_text_output(tmp_path):
    result = run_cli(tmp_path)
    assert result.returncode == 0
    assert '1 | user' in result.stdout
    assert 'name: alice' in result.stdout


def test_hide_line_numbers_text(tmp_path):
    result = run_cli(tmp_path, '--hide-line-numbers')
    assert result.returncode == 0
    assert '1 |' not in result.stdout
    assert 'user' in result.stdout


def test_search_values_only_path(tmp_path):
    result = run_cli(tmp_path, '--search-vals', 'alice', '--hide-line-numbers')
    assert result.returncode == 0
    assert 'user' in result.stdout
    assert 'name: alice' in result.stdout
    assert 'token' not in result.stdout


def test_include_search_children(tmp_path):
    result = run_cli(tmp_path, '--search-keys', 'profile', '--include-search-children', '--hide-line-numbers')
    assert result.returncode == 0
    assert 'profile' in result.stdout
    assert 'bio:' in result.stdout


def test_hide_exact_overrides_display(tmp_path):
    result = run_cli(tmp_path, '--search-vals', 'abc123', '--hide-fields-matching', 'token', '--hide-line-numbers')
    assert result.returncode == 0
    assert 'token: [hidden]' in result.stdout


def test_hide_contains_overrides_display(tmp_path):
    result = run_cli(tmp_path, '--search-vals', 'deep hidden', '--hide-fields-containing', 'secret', '--hide-line-numbers')
    assert result.returncode == 0
    assert 'secretNote: [hidden]' in result.stdout


def test_truncation_text(tmp_path):
    result = run_cli(tmp_path, '--truncate-line-length', '12', '--hide-line-numbers')
    assert result.returncode == 0
    assert '…' in result.stdout
    assert 'long:' in result.stdout


def test_output_json_has_no_line_numbers(tmp_path):
    result = run_cli(tmp_path, '--output', 'json')
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert 'user' in payload
    assert '1 |' not in result.stdout


def test_output_json_ignores_line_number_flag(tmp_path):
    result = run_cli(tmp_path, '--output', 'json', '--hide-line-numbers')
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert 'system' in payload


def test_output_csv_without_line_numbers(tmp_path):
    result = run_cli(tmp_path, '--output', 'csv', '--hide-line-numbers')
    assert result.returncode == 0
    rows = list(csv.reader(io.StringIO(result.stdout)))
    assert rows[0][0] == 'user'


def test_output_csv_with_line_numbers(tmp_path):
    result = run_cli(tmp_path, '--output', 'csv')
    assert result.returncode == 0
    rows = list(csv.reader(io.StringIO(result.stdout)))
    assert rows[0][0] == '1'
    assert rows[0][1] == 'user'


def test_output_csv_is_rfc_safe(tmp_path):
    result = run_cli(tmp_path, '--output', 'csv', '--hide-line-numbers')
    assert result.returncode == 0
    rows = list(csv.reader(io.StringIO(result.stdout)))
    flat = [' | '.join(row) for row in rows]
    assert any('loves synths, math, and "quotes"' in row for row in flat)


def test_output_csv_truncates_cells(tmp_path):
    result = run_cli(tmp_path, '--output', 'csv', '--truncate-line-length', '10', '--hide-line-numbers')
    assert result.returncode == 0
    rows = list(csv.reader(io.StringIO(result.stdout)))
    assert any(cell.endswith('…') for row in rows for cell in row)


def test_show_schema_alone(tmp_path):
    result = run_cli(tmp_path, '--show-schema')
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload['user']['name'] == 'str'


def test_show_schema_rejects_other_arguments(tmp_path):
    result = run_cli(tmp_path, '--show-schema', '--search-vals', 'alice')
    assert result.returncode == 2
    assert '--show-schema not compatible with other arguments' in result.stderr


def test_no_matches(tmp_path):
    result = run_cli(tmp_path, '--search-vals', 'zzzz-not-present', '--hide-line-numbers')
    assert result.returncode == 0
    assert result.stdout.strip() == '<no matches>'


def test_combination_search_hide_include_json(tmp_path):
    result = run_cli(
        tmp_path,
        '--output', 'json',
        '--search-keys', 'user',
        '--include-search-children',
        '--hide-fields-matching', 'token'
    )
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload['user']['token'] == '[hidden]'
    assert payload['user']['name'] == 'alice'


def test_array_items_render_in_text(tmp_path):
    result = run_cli(tmp_path, '--search-vals', 'purchase', '--hide-line-numbers')
    assert result.returncode == 0
    assert '[1]' in result.stdout
    assert 'type: purchase' in result.stdout
