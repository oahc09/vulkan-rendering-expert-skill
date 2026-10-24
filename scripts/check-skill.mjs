#!/usr/bin/env node
// Repository checks only: no model calls, GPU execution, writes, or dependencies.
import { execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { existsSync, readFileSync } from 'node:fs';
import { dirname, extname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const args = process.argv.slice(2);
let maxFiles;
if (args.length) {
  if (args.length !== 2 || args[0] !== '--max-files' || !/^[1-9]\d*$/.test(args[1])) {
    console.error('Usage: node scripts/check-skill.mjs [--max-files N]');
    process.exit(2);
  }
  maxFiles = Number(args[1]);
}

function git(...options) {
  return execFileSync('git', ['-C', root, ...options], { encoding: 'utf8' }).trim();
}

let files;
let revision;
try {
  // Include pending additions, exclude ignored local reports and fixtures.
  files = [...new Set(git('ls-files', '--cached', '--others', '--exclude-standard', '-z')
    .split('\0').filter(Boolean))].sort();
  revision = git('rev-parse', 'HEAD');
} catch (error) {
  console.error(`Cannot inspect Git checkout: ${error.message}`);
  process.exit(2);
}

const errors = [];
const documents = new Map();
const decoder = new TextDecoder('utf-8', { fatal: true });
for (const name of files) {
  if (extname(name) !== '.md') continue;
  const path = resolve(root, name);
  if (!existsSync(path)) {
    errors.push(`${name}: listed in Git but missing from checkout`);
    continue;
  }
  try {
    const data = readFileSync(path);
    if (data[0] === 0xef && data[1] === 0xbb && data[2] === 0xbf) {
      errors.push(`${name}: UTF-8 BOM`);
    }
    const text = decoder.decode(data);
    documents.set(name, text);
    // Markdown closing fences must use the same marker and at least its length.
    let fence;
    for (const line of text.split(/\r?\n/)) {
      const match = /^ {0,3}(`{3,}|~{3,})(.*)$/.exec(line);
      if (!match) continue;
      if (!fence) fence = match[1];
      else if (match[1][0] === fence[0] && match[1].length >= fence.length && !match[2].trim()) fence = undefined;
    }
    if (fence) errors.push(`${name}: unclosed code fence`);
  } catch (error) {
    errors.push(`${name}: cannot decode/read UTF-8 (${error.message})`);
  }
}

let localLinks = 0;
for (const [name, text] of documents) {
  const prose = text.replace(/^ {0,3}(`{3,}|~{3,})[^\n]*\n[\s\S]*?^ {0,3}\1\s*$/gm, '');
  // Only ordinary inline Markdown file links; no guesses about prose paths or anchors.
  for (const match of prose.matchAll(/!?\[[^\]\n]*\]\((<[^>\n]+>|[^\s)]+)(?:\s+"[^"\n]*")?\)/g)) {
    const target = match[1].replace(/^<|>$/g, '');
    if (/^(?:[a-z][\w+.-]*:|\/\/|#)/i.test(target)) continue;
    let path;
    try { path = decodeURIComponent(target.split(/[?#]/)[0]); }
    catch { errors.push(`${name}: invalid URL encoding in ${target}`); continue; }
    if (!path) continue;
    localLinks++;
    if (!existsSync(resolve(root, dirname(name), path))) errors.push(`${name}: missing link ${target}`);
  }
}

const entry = documents.get('SKILL.md') ?? '';
if (!/^---\r?\n[\s\S]*?\r?\n---(?:\r?\n|$)/.test(entry)) errors.push('SKILL.md: missing frontmatter block');
for (const field of ['name', 'description']) {
  if (!new RegExp(`^${field}:\\s*\\S.*$`, 'm').test(entry.split(/\r?\n---/)[0])) {
    errors.push(`SKILL.md: missing nonempty ${field}`);
  }
}
const routes = new Set([...entry.matchAll(/`(references\/[^`\n]+)`/g)].map(match => match[1]));
for (const route of routes) {
  if (!existsSync(resolve(root, route))) errors.push(`SKILL.md: missing route ${route}`);
}

const summary = documents.get('references/MODULE_SUMMARY.md') ?? '';
const modules = [...summary.matchAll(/^- `(\d\d_[^`]+)`: (\d+) files\s*$/gm)];
const actualModules = new Set(files.map(name => /^references\/(\d\d_[^/]+)\//.exec(name)?.[1]).filter(Boolean));
if (modules.length !== actualModules.size || new Set(modules.map(row => row[1])).size !== modules.length) {
  errors.push('MODULE_SUMMARY: missing or duplicate module entries');
}
for (const [, module, expected] of modules) {
  const actual = files.filter(name => name.startsWith(`references/${module}/`)).length;
  if (actual !== Number(expected)) errors.push(`MODULE_SUMMARY: ${module}: expected ${expected}, found ${actual}`);
  if (!documents.has(`references/${module}/README.md`)) errors.push(`${module}: missing README.md`);
}
if (maxFiles && files.length > maxFiles) errors.push(`File budget: ${files.length} > ${maxFiles}`);

// Identity of evaluated knowledge, not a claim of API correctness or model behavior.
// Exclude this execution record to avoid a self-referential hash.
const sourceFiles = files.filter(name => name === 'SKILL.md' || name.startsWith('agents/') ||
  (name.startsWith('references/') && name !== 'references/07_integration_pack/behavior_evaluation.md'));
const fingerprint = createHash('sha256');
for (const name of sourceFiles) {
  if (!existsSync(resolve(root, name))) continue;
  fingerprint.update(name).update('\0').update(readFileSync(resolve(root, name))).update('\0');
}

console.log(JSON.stringify({
  status: errors.length ? 'FAIL' : 'PASS', revision,
  files: files.length, markdownFiles: documents.size, localLinks, entryRoutes: routes.size,
  sourceSha256: fingerprint.digest('hex'), fingerprintFiles: sourceFiles.length,
  scope: 'Git-visible files, UTF-8, fences, inline local file links, entry routes, module counts; no YAML schema, anchor, remote URL, Vulkan runtime, or model behavior validation',
  errors,
}, null, 2));
process.exitCode = errors.length ? 1 : 0;
