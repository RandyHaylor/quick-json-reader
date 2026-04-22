const test = require('node:test');
const assert = require('node:assert/strict');
const { spawnSync } = require('node:child_process');
const path = require('node:path');
const mod = require('../src/quick_json_reader.js');

const CLI_PATH = path.join(__dirname, '..', 'src', 'quick_json_reader.js');
const SAMPLE_INPUT_PATH = path.join(__dirname, '..', 'examples', 'sample_easy_json_reader_input.json');

const sample = {
  user: {
    name: 'alice',
    token: 'abc123',
    nested: { secret: 'hidden_value' }
  },
  system: { status: 'ok' }
};

test('supports in-memory text rendering', () => {
  const result = mod.runWithValue(sample, { output: 'txt' });
  assert.match(result.outputText, /user/);
  assert.match(result.outputText, /alice/);
});

test('supports json output without line numbers', () => {
  const result = mod.runWithValue(sample, { output: 'json', showLineNumbers: true });
  assert.doesNotMatch(result.outputText, /\|/);
  assert.match(result.outputText, /"user"/);
});

test('enforces schema isolation', () => {
  assert.throws(
    () => mod.runWithValue(sample, { showSchema: true, searchVals: ['alice'] }),
    /--show-schema not compatible with other arguments/
  );
});

test('exclude fully removes matching branch from output', () => {
  const result = mod.runWithValue(sample, {
    output: 'txt',
    excludeFieldsMatching: ['nested']
  });
  assert.match(result.outputText, /user/);
  assert.doesNotMatch(result.outputText, /nested/);
  assert.doesNotMatch(result.outputText, /secret/);
  assert.doesNotMatch(result.outputText, /hidden_value/);
});

test('exclude works with containing-match on scalar fields', () => {
  const result = mod.runWithValue(sample, {
    output: 'txt',
    excludeFieldsContaining: ['tok']
  });
  assert.match(result.outputText, /name/);
  assert.doesNotMatch(result.outputText, /token/);
  assert.doesNotMatch(result.outputText, /abc123/);
});

test('CLI accepts --exclude-fields-matching and omits the field', () => {
  const result = spawnSync('node', [CLI_PATH, SAMPLE_INPUT_PATH, '--exclude-fields-matching', 'password', 'token'], { encoding: 'utf8' });
  assert.equal(result.status, 0);
  assert.doesNotMatch(result.stdout, /password/);
  assert.doesNotMatch(result.stdout, /token/);
  assert.doesNotMatch(result.stdout, /\[hidden\]/);
});

test('parseArgs accepts --show-app-log flag', () => {
  assert.doesNotThrow(() => mod.parseArgs(['some-file.json', '--show-app-log']));
});

test('CLI is silent on stderr by default', () => {
  const result = spawnSync('node', [CLI_PATH, SAMPLE_INPUT_PATH], { encoding: 'utf8' });
  assert.equal(result.status, 0);
  assert.equal(result.stderr, '');
  assert.match(result.stdout, /user/);
});

test('CLI emits progress logs to stderr with --show-app-log', () => {
  const result = spawnSync('node', [CLI_PATH, SAMPLE_INPUT_PATH, '--show-app-log'], { encoding: 'utf8' });
  assert.equal(result.status, 0);
  assert.match(result.stderr, /performing parse/);
  assert.match(result.stderr, /render complete/);
  assert.match(result.stdout, /user/);
});

test('showStats prepends stat lines to txt output', () => {
  const result = mod.runWithValue(sample, { output: 'txt', showStats: true });
  const lines = result.outputText.split('\n');
  assert.match(lines[0], /^total char count: \d+$/);
  assert.match(lines[1], /^nesting depth: \d+$/);
  assert.match(lines[2], /^total objects: \d+$/);
  assert.match(lines[3], /^total arrays: \d+$/);
  assert.equal(lines[4], 'json-valid: true');
});

test('showStats in json output yields valid json with jsonStats first', () => {
  const result = mod.runWithValue(sample, { output: 'json', showStats: true });
  const parsed = JSON.parse(result.outputText);
  const firstKey = Object.keys(parsed)[0];
  assert.equal(firstKey, 'jsonStats');
  assert.equal(parsed.jsonStats.jsonValid, true);
  assert.equal(typeof parsed.jsonStats.totalCharCount, 'number');
  assert.equal(typeof parsed.jsonStats.nestingDepth, 'number');
  assert.equal(typeof parsed.jsonStats.totalObjects, 'number');
  assert.equal(typeof parsed.jsonStats.totalArrays, 'number');
  assert.ok('user' in parsed);
});

test('CLI --show-stats prepends stats to txt stdout', () => {
  const result = spawnSync('node', [CLI_PATH, SAMPLE_INPUT_PATH, '--show-stats'], { encoding: 'utf8' });
  assert.equal(result.status, 0);
  const lines = result.stdout.split('\n');
  assert.match(lines[0], /^total char count: \d+$/);
  assert.match(lines[4], /^json-valid: true$/);
});

test('CLI --show-stats --output json yields valid json starting with jsonStats', () => {
  const result = spawnSync('node', [CLI_PATH, SAMPLE_INPUT_PATH, '--show-stats', '--output', 'json'], { encoding: 'utf8' });
  assert.equal(result.status, 0);
  const parsed = JSON.parse(result.stdout);
  assert.equal(Object.keys(parsed)[0], 'jsonStats');
  assert.equal(parsed.jsonStats.jsonValid, true);
});

test('--show-schema cannot be combined with --show-stats', () => {
  assert.throws(
    () => mod.parseArgs(['file.json', '--show-schema', '--show-stats']),
    /not compatible/
  );
});

test('runWithValue does not emit to stderr even if gate was previously on', () => {
  const chunks = [];
  const originalWrite = process.stderr.write.bind(process.stderr);
  process.stderr.write = (chunk) => {
    chunks.push(String(chunk));
    return true;
  };
  try {
    mod.runWithValue(sample, { output: 'txt' });
  } finally {
    process.stderr.write = originalWrite;
  }
  assert.equal(chunks.join(''), '');
});
