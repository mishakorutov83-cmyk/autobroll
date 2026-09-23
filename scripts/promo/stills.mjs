// QA stills for a promo ad: bundle once, render many frames.
//   node scripts/promo/stills.mjs <promo-id> 0,60,300
import path from 'node:path';
import fs from 'node:fs';
import {bundle} from '@remotion/bundler';
import {renderStill, selectComposition} from '@remotion/renderer';

const [id, list] = process.argv.slice(2);
const root = path.resolve(import.meta.dirname, '../..');
const inputProps = JSON.parse(fs.readFileSync(path.join(root, 'public', `${id}.promo.json`), 'utf8'));
const serveUrl = await bundle({entryPoint: path.join(root, 'src/index.ts'), publicDir: path.join(root, 'public')});
const composition = await selectComposition({serveUrl, id: 'Promo', inputProps});
fs.mkdirSync(path.join(root, 'out'), {recursive: true});
for (const f of list.split(',').map(Number)) {
  const output = path.join(root, 'out', `${id}_f${f}.png`);
  await renderStill({serveUrl, composition, inputProps, frame: Math.min(f, composition.durationInFrames - 1), output});
  console.log(output);
}
