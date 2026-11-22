// Migrate an archived cobalt recording to the selected carmine palette without
// re-running checks or posting messages. Input and output must be different files.
// Usage: node tools/recolor-legacy.mjs original.mp4 carmine.mp4
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {spawnSync} from 'node:child_process';

const [input, output, preview] = process.argv.slice(2);
if (!input || !output || path.resolve(input) === path.resolve(output)) {
  throw new Error('Provide distinct input.mp4 and output.mp4 paths. Always use the original recording as input.');
}
const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'prawdowid-carmine-'));
const cube = path.join(dir, 'brand.cube');
const clamp = x => Math.max(0, Math.min(1, x));
const smooth = (a, b, x) => { const t = clamp((x-a)/(b-a)); return t*t*(3-2*t); };
function map(rgb) {
  const [r,g,b] = rgb, max = Math.max(...rgb), min = Math.min(...rgb), d=max-min;
  let h = !d ? 0 : max === r ? ((g-b)/d+6)%6*60 : max === g ? ((b-r)/d+2)*60 : ((r-g)/d+4)*60;
  // Cobalt is around 243 degrees; Discord's native blurple is around 235.
  const mask=smooth(235,238,h)*(1-smooth(258,268,h))*smooth(.015,.08,max ? d/max : 0);
  const t=(b-Math.min(r,g))/(182/255);
  let result=rgb.map((v,i)=>v*(1-mask)+clamp(b-(242/255-[201,39,67][i]/255)*t)*mask);
  for(const [from,to] of [[[244,243,235],[250,245,236]],[[227,231,213],[240,220,224]]]) {
    const distance=Math.hypot(...rgb.map((v,i)=>v-from[i]/255));
    const weight=(1-smooth(.015,.075,distance))*(1-mask);
    result=result.map((v,i)=>clamp(v+(to[i]-from[i])/255*weight));
  }
  return result;
}
const size=65, lines=['TITLE "Prawdowid juicy carmine"',`LUT_3D_SIZE ${size}`];
for(let b=0;b<size;b++) for(let g=0;g<size;g++) for(let r=0;r<size;r++) {
  lines.push(map([r/(size-1),g/(size-1),b/(size-1)]).map(x=>x.toFixed(6)).join(' '));
}
fs.writeFileSync(cube, lines.join('\n'));
try {
  const run=spawnSync('ffmpeg',['-hide_banner','-loglevel','warning','-y','-i',input,
    ...(preview === '--preview' ? ['-t','5'] : []),
    '-map','0:v:0','-map','0:a?','-vf',`lut3d=file=${cube}:interp=tetrahedral`,
    '-c:v','libx264','-preset','veryfast','-crf','17','-pix_fmt','yuv420p','-c:a','copy',
    '-movflags','+faststart',output],{stdio:'inherit'});
  if(run.error) throw run.error;
  if(run.status!==0) throw new Error(`ffmpeg exited with ${run.status}`);
  console.log(`Saved carmine recording: ${output}`);
} finally {fs.rmSync(dir,{recursive:true,force:true});}
