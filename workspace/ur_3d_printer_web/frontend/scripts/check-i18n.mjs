#!/usr/bin/env node
/**
 * Build-time i18n guard.
 *
 * Fails the build if any translation key referenced in the source is missing
 * from a locale file, or if the locale files have drifted apart. Without this
 * the symptom only shows up in the browser, and it shows up as the raw key id
 * rendered as UI text ("test.simulationMode"), which is easy to mistake for a
 * caching problem — so catching it at build time is worth the few ms.
 *
 * Runs as part of `npm run build` (see package.json), which is what the
 * Docker image build invokes.
 */
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const SRC = join(root, 'src');
const LOCALES = join(root, 'public', 'locales');

// Keys built dynamically from runtime values, always with a literal fallback
// (e.g. t(`state.${name}`, name)) — they can't be verified statically and
// degrade gracefully by design.
const DYNAMIC_PREFIXES = ['state.', 'extruder.state.'];

function walk(dir) {
  return readdirSync(dir).flatMap((entry) => {
    const p = join(dir, entry);
    return statSync(p).isDirectory() ? walk(p) : [p];
  });
}

function flatten(obj, prefix = '') {
  return Object.entries(obj).flatMap(([k, v]) =>
    v !== null && typeof v === 'object'
      ? flatten(v, `${prefix}${k}.`)
      : [`${prefix}${k}`],
  );
}

const used = new Set();
const keyPattern = /\bt\(\s*['"`]([A-Za-z0-9_.]+)['"`]/g;
for (const file of walk(SRC).filter((f) => /\.tsx?$/.test(f))) {
  const text = readFileSync(file, 'utf8');
  for (const m of text.matchAll(keyPattern)) used.add(m[1]);
}

const langs = readdirSync(LOCALES);
const locales = Object.fromEntries(
  langs.map((lang) => [
    lang,
    new Set(flatten(JSON.parse(readFileSync(join(LOCALES, lang, 'translation.json'), 'utf8')))),
  ]),
);

const problems = [];
for (const lang of langs) {
  const missing = [...used]
    .filter((k) => !DYNAMIC_PREFIXES.some((p) => k.startsWith(p)))
    .filter((k) => !locales[lang].has(k))
    .sort();
  if (missing.length) {
    problems.push(`  [${lang}] missing ${missing.length} key(s):\n${missing.map((k) => `      ${k}`).join('\n')}`);
  }
}

// Cross-language drift: a key present in one locale but not another means one
// language silently falls back and renders in the wrong language.
for (const a of langs) {
  for (const b of langs) {
    if (a >= b) continue;
    const onlyA = [...locales[a]].filter((k) => !locales[b].has(k)).sort();
    const onlyB = [...locales[b]].filter((k) => !locales[a].has(k)).sort();
    if (onlyA.length || onlyB.length) {
      problems.push(
        `  [${a} vs ${b}] out of sync:\n` +
          (onlyA.length ? `      only in ${a}: ${onlyA.join(', ')}\n` : '') +
          (onlyB.length ? `      only in ${b}: ${onlyB.join(', ')}` : ''),
      );
    }
  }
}

if (problems.length) {
  console.error(`\n✗ i18n check failed (${used.size} keys referenced in src/):\n`);
  console.error(problems.join('\n'));
  console.error('\nAdd the missing keys to every file under public/locales/.\n');
  process.exit(1);
}

console.log(`✓ i18n check passed — ${used.size} keys, locales [${langs.join(', ')}] complete and in sync`);
