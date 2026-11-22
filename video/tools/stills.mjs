// Renders single frames of the composition for a quick visual check:
//   node tools/stills.mjs <outDir> <frame> [<frame> …]
import {bundle} from '@remotion/bundler';
import {renderStill, selectComposition} from '@remotion/renderer';
import fs from 'node:fs';
import path from 'node:path';

const [outDir, ...frames] = process.argv.slice(2);
fs.mkdirSync(outDir, {recursive: true});
const serveUrl = await bundle({entryPoint: path.resolve('src/index.ts')});
const composition = await selectComposition({serveUrl, id: 'Demo'});
for (const f of frames.map(Number)) {
  const output = path.join(outDir, `f${String(f).padStart(5, '0')}.png`);
  await renderStill({composition, serveUrl, frame: f, output, imageFormat: 'png'});
  console.log(output);
}
