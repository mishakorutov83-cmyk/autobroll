// QA stills in one process: bundle once, render many frames (vs ~30 s per `remotion still`).
//   node scripts/reel/stills.mjs <episode-id> 60,300,1500
import path from 'node:path';
import fs from 'node:fs';
import {bundle} from '@remotion/bundler';
import {renderStill, selectComposition} from '@remotion/renderer';

const [ep, list] = process.argv.slice(2);
const root = path.resolve(import.meta.dirname, '../..');
const inputProps = JSON.parse(fs.readFileSync(path.join(root, 'public', `${ep}.props.json`), 'utf8'));
const serveUrl = await bundle({entryPoint: path.join(root, 'src/index.ts'), publicDir: path.join(root, 'public')});
const composition = await selectComposition({serveUrl, id: 'MultiClip', inputProps});
fs.mkdirSync(path.join(root, 'out'), {recursive: true});
for (const f of list.split(',').map(Number)) {
  const output = path.join(root, 'out', `${ep}_f${f}.png`);
  await renderStill({serveUrl, composition, inputProps, frame: Math.min(f, composition.durationInFrames - 1), output});
  console.log(output);
}
fs.rmSync(serveUrl, {recursive: true, force: true}); // bundle holds a copy of public/
