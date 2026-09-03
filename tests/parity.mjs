// node tests/parity.mjs — load the classic-script JS engine into this context and compare with golden.json.
import fs from 'node:fs';
import path from 'node:path';
import url from 'node:url';
import vm from 'node:vm';

const root = path.resolve(path.dirname(url.fileURLToPath(import.meta.url)), '..');
const scripts = [
  'data/gen/tables.gen.js', 'data/gen/chars.gen.js', 'src/vendor/lunar.js',
  'src/js/core/wuge.js', 'src/js/core/dayan.js', 'src/js/core/sancai.js', 'src/js/core/yinyun.js',
  'src/js/core/chars.js', 'src/js/core/rating.js', 'src/js/core/bazi.js', 'src/js/core/generator.js',
  'tests/parity_core.js',
];
for (const rel of scripts) {
  vm.runInThisContext(fs.readFileSync(path.join(root, rel), 'utf8'), { filename: rel });
}
const golden = JSON.parse(fs.readFileSync(path.join(root, 'tests/fixtures/golden.json'), 'utf8'));
const t0 = Date.now();
const res = globalThis.NovaParity.run(golden, globalThis.Nova);
const ms = Date.now() - t0;
console.log(`parity: ${res.pass}/${res.total} pass in ${ms} ms (golden ${golden.meta.generated}, chars ${golden.meta.chars_generated})`);
for (const f of res.fails.slice(0, 10)) {
  console.log(`FAIL [${f.section}] input=${JSON.stringify(f.input)}`);
  console.log(`  expect=${JSON.stringify(f.expect).slice(0, 600)}`);
  console.log(`  got   =${JSON.stringify(f.got).slice(0, 600)}`);
}
if (res.fails.length > 10) console.log(`... ${res.fails.length - 10} more failures`);
process.exit(res.fails.length ? 1 : 0);
