// Preview-only rendering of the existing product. Production files are read, never written.
import fs from 'node:fs/promises';
import path from 'node:path';
import http from 'node:http';
import {createRequire} from 'node:module';
const require = createRequire('/Users/pawelczajczyk/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/');
const {chromium} = require('playwright');
const root = path.resolve(import.meta.dirname, '../..');
const more = process.argv.includes('--more');
const red = process.argv.includes('--red');
const reference = process.argv.includes('--reference');
const sea = process.argv.includes('--sea');
const carmine = process.argv.includes('--carmine');
const out = carmine ? path.join(import.meta.dirname,'karmin-warianty') : sea ? path.join(import.meta.dirname,'morski') : reference ? path.join(import.meta.dirname,'twoja-paleta') : red ? path.join(import.meta.dirname,'czerwienie') : more ? path.join(import.meta.dirname,'kolejne') : import.meta.dirname;
await fs.mkdir(out,{recursive:true});
const palettes = carmine ? [
  {id:'11-karmin', name:'11 / Karmin — punkt odniesienia', brand:'#b9233e', deep:'#8d152c', paper:'#f7f2e8', soft:'#eddcda', desc:'Oryginał do porównania: nasycony karmin z chłodną nutą i jasna kość słoniowa.'},
  {id:'21-karmin-cieply', name:'21 / Karmin i ciepły krem', brand:'#bb2d35', deep:'#8f1e28', paper:'#faf0e2', soft:'#edd9ce', desc:'Nieco cieplejsza czerwień, mniej różowa. Kremowe tło podkreśla charakter drukowanej ryciny.'},
  {id:'22-karmin-gleboki', name:'22 / Głęboki karmin', brand:'#9f2038', deep:'#76152a', paper:'#f5efe4', soft:'#e7d5d2', desc:'Ciemniejszy i spokojniejszy od oryginału. Mocny kontrast, elegancki charakter i cieplejszy papier.'},
  {id:'23-karmin-soczysty', name:'23 / Soczysty karmin', brand:'#c92743', deep:'#9c1a32', paper:'#faf5ec', soft:'#f0dce0', desc:'Jaśniejsza, bardziej nasycona czerwień na delikatniejszej kości słoniowej. Najbardziej wyrazisty wariant tej rodziny.'},
  {id:'24-karmin-malinowy', name:'24 / Karmin z nutą maliny', brand:'#b12650', deep:'#851b3b', paper:'#f8f1ed', soft:'#edd9df', desc:'Subtelne przesunięcie w stronę maliny. Chłodniejszy, lżejszy odbiór przy zachowaniu mocnego czerwonego akcentu.'},
  {id:'25-karmin-przygaszony', name:'25 / Karmin na starym papierze', brand:'#a33d48', deep:'#7e2a35', paper:'#f2ece0', soft:'#e5d7cc', desc:'Mniej nasycony, miękki karmin i ciemniejszy papier. Najspokojniejsza, lekko nostalgiczna interpretacja oryginału.'}
] : sea ? [
  {id:'20-morski', name:'20 / Morski i jasny papier', brand:'#08777c', deep:'#07565b', paper:'#f2f1e8', soft:'#d4e5de', desc:'Głęboki morski turkus na ilustracji, nagłówkach i przyciskach. Jasny, ciepły papier oraz subtelna morska zieleń w zakładkach i objaśnieniach.'}
] : reference ? [
  {id:'17-piasek', name:'17 / Piasek i czerwień', brand:'#81231e', deep:'#2b2c1e', paper:'#cab891', soft:'#e5dbc5', surface:'#e5dbc5', art:'#81231e', desc:'Najwierniejszy kolorystyce referencji: piaskowe tło, ciemnoczerwona rycina, oliwkowe i szałwiowe belki. Ciemny tekst i ramki z palety.'},
  {id:'18-papier', name:'18 / Papier i czerwień', brand:'#81231e', deep:'#81231e', paper:'#f3eee2', soft:'#cab891', surface:'#f3eee2', art:'#81231e', desc:'Mój wybór: rozjaśniony papier daje oddech ilustracji. Piasek w zakładkach, oliwka w belkach, szałwia w objaśnieniach; czerwień prowadzi do działania.'},
  {id:'19-szalwia', name:'19 / Szałwia i czerwień', brand:'#81231e', deep:'#81231e', paper:'#ede7d8', soft:'#cab891', surface:'#ede7d8', art:'#5f6a54', desc:'Spokojniejsza, szałwiowa rycina i czerwone przyciski. Zieleń w sekcji objaśnień, oliwkowe detale i piaskowe zakładki równoważą czerwień.'}
] : red ? [
  {id:'11-karmin', name:'11 / Karmin i kość słoniowa', brand:'#b9233e', deep:'#8d152c', paper:'#f7f2e8', soft:'#eddcda', desc:'Mój wybór: nasycona czerwień z chłodną nutą. Wyrazista, graficzna i dobrze współgrająca z kremowym papierem.'},
  {id:'12-cynober', name:'12 / Cynober i krem', brand:'#bd3b27', deep:'#942a1c', paper:'#faf2e6', soft:'#f0ddc8', desc:'Najbardziej energetyczna propozycja. Ciepła czerwień w stronę pomarańczu, z charakterem drukowanego plakatu.'},
  {id:'13-cegla', name:'13 / Cegła i len', brand:'#9b4536', deep:'#723025', paper:'#f4efe3', soft:'#e8d9ca', desc:'Przygaszona, ziemista czerwień. Spokojniejsza, bardziej dojrzała alternatywa dla intensywnego karminu.'},
  {id:'14-malina', name:'14 / Malina i porcelana', brand:'#a52b57', deep:'#7c1d40', paper:'#f8f1ef', soft:'#eed9e2', desc:'Chłodniejszy odcień czerwieni z różową nutą. Lekki, redakcyjny i mniej kojarzący się z alarmem.'},
  {id:'15-wino', name:'15 / Wino i pergamin', brand:'#6e2336', deep:'#4e1725', paper:'#f4eee4', soft:'#e5d5d6', desc:'Najciemniejsza czerwień w zestawie. Kameralna, elegancka, z atmosferą biblioteki i dawnej ryciny.'},
  {id:'16-sangwina', name:'16 / Sangwina i piasek', brand:'#8c3028', deep:'#63201b', paper:'#f6eee0', soft:'#e9d6c1', desc:'Głęboka, ciepła czerwień pigmentu. Mocny duoton, który szczególnie dobrze wydobywa fakturę ilustracji.'}
] : more ? [
  {id:'05-grafit', name:'05 / Grafit i wanilia', brand:'#353734', deep:'#20221f', paper:'#f5f2e8', soft:'#ece1ad', desc:'Najbardziej oszczędny: grafitowa ilustracja i waniliowe akcenty. Techniczny, mocny i ponadczasowy.'},
  {id:'06-oliwka', name:'06 / Oliwka i len', brand:'#626021', deep:'#444316', paper:'#f4f0e1', soft:'#e5e2bf', desc:'Wyraźnie żółtozielony kierunek. Przywodzi na myśl atlas, bibliotekę i papierowe archiwum.'},
  {id:'07-bordo', name:'07 / Bordo i różany papier', brand:'#7a2946', deep:'#591b32', paper:'#f7efeb', soft:'#ead6dd', desc:'Szlachetny i zdecydowany, z charakterem redakcji. Bordo marki wymaga wyraźnego oddzielenia od czerwieni fałszu.'},
  {id:'08-kakao', name:'08 / Kakao i owies', brand:'#674a36', deep:'#483224', paper:'#f4eee2', soft:'#e4d5bd', desc:'Najcieplejszy, spokojny duoton. Dobrze podkreśla rycinę i daje efekt starego druku.'},
  {id:'09-ametyst', name:'09 / Ametyst i kreda', brand:'#704695', deep:'#50316e', paper:'#f4f0f3', soft:'#e3d9ec', desc:'Bardziej współczesny i wyrazisty fiolet. Zachowuje cyfrowy charakter bez niebieskiego akcentu.'},
  {id:'10-bursztyn', name:'10 / Bursztyn i krem', brand:'#805c08', deep:'#5b4004', paper:'#faf3e3', soft:'#eddfa9', desc:'Złocisty, ciepły i plakatowy. Przygaszony bursztyn utrzymuje czytelność tekstów i przycisków.'}
] : [
  {id:'01-oberzyna', name:'01 / Oberżyna i pergamin', brand:'#63365b', deep:'#472541', paper:'#f4f0e8', soft:'#e9dfeb', desc:'Mój wybór: wyrazisty, redakcyjny charakter. Kolor marki wyraźnie oddzielony od ocen prawda / fałsz.'},
  {id:'02-petrol', name:'02 / Petrol i kość słoniowa', brand:'#176568', deep:'#10494c', paper:'#f1f3eb', soft:'#dce8df', desc:'Spokojny i rzeczowy. Najbliższy narzędziu analitycznemu, z chłodnym, przygaszonym akcentem.'},
  {id:'03-las', name:'03 / Las i papier', brand:'#40583b', deep:'#2d4029', paper:'#f2f0e5', soft:'#e2e5d2', desc:'Stonowany, archiwalny i ciepły. Najbardziej naturalne połączenie z papierem i grafiką rastrową.'},
  {id:'04-miedz', name:'04 / Miedź i piasek', brand:'#964b2d', deep:'#71351f', paper:'#f7f0e5', soft:'#eddfc9', desc:'Ciepły, odważny i plakatowy. Najmocniej zmienia odbiór dotychczasowej identyfikacji.'}
];
const mime = {'.html':'text/html','.css':'text/css','.js':'text/javascript','.png':'image/png','.svg':'image/svg+xml','.woff2':'font/woff2','.webmanifest':'application/json'};
function recolor(s,p) {
 // Normalize the implemented palette so historical alternatives remain renderable.
 s=s.replaceAll('#c92743','#443cf2').replaceAll('#9c1a32','#3027cf').replaceAll('#faf5ec','#f4f3eb').replaceAll('#f0dce0','#e3e7d5');
 let result=s.replaceAll('#443cf2',p.brand).replaceAll('#3027cf',p.deep).replaceAll('#f4f3eb',p.paper).replaceAll('#e3e7d5',p.soft).replaceAll('#e0eaff',p.soft).replaceAll('#1d3557',p.deep).replaceAll('#2f5d8a',p.deep).replaceAll('#eff8ff',p.soft).replaceAll('#b2ddff',p.brand);
 if(reference){
  result=result.replaceAll('#191919','#2b2c1e').replaceAll('#55554f','#454638').replaceAll('#c4c3ba','#a99d7b');
  if(s.includes('Prawdowid desktop')) result+=`\n:root{--ink:#2b2c1e;--muted:#454638;--line:#a99d7b;--card:${p.surface}}body{background-image:radial-gradient(#70683b55 .65px,transparent .8px),radial-gradient(#5f6a5433 .6px,transparent .8px)}.source-window>.window-bar{background:#70683b;color:#f3eee2}.how-window>.window-bar{background:#5f6a54;color:#f3eee2}.honest-note{background:#cab891;color:#2b2c1e}.hero-content h1{color:${p.art}}textarea{background:#f6f1e6}.how-window .window-body{${p.id==='19-szalwia'?'background:#5f6a54;color:#f3eee2':''}}${p.id==='19-szalwia'?'.how-window .window-body>h2,.how-window .text-link{color:#f3eee2}':''}`;
 }
 return result;
}
const server = http.createServer(async(req,res)=>{
 try {
  const u=new URL(req.url,'http://localhost');
  const p=palettes.find(p=>p.id===u.searchParams.get('palette')) || palettes[0];
  let rel=decodeURIComponent(u.pathname);
  if(rel==='/') rel='/index.html';
  if(!path.extname(rel)) rel+='.html';
  const file=path.resolve(root, rel.startsWith('/extension/')?'.'+rel:'web'+rel);
  if(!file.startsWith(root+path.sep)) throw Error();
  let body=await fs.readFile(file);
  const ext=path.extname(file);
  if(['.html','.css','.js'].includes(ext)) body=recolor(body.toString(),p);
  res.writeHead(200,{'Content-Type':mime[ext]||'application/octet-stream'});res.end(body);
 } catch {res.writeHead(404);res.end('Preview: resource unavailable');}
});
await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
const origin=`http://127.0.0.1:${server.address().port}`;
const browser=await chromium.launch({executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless:true});
const page=await browser.newPage({viewport:{width:1440,height:1050},deviceScaleFactor:1,serviceWorkers:'block'});
const checks=[];
for(const p of palettes){
 await page.goto(`${origin}/?palette=${p.id}`);
 // Keep all requests on the chosen palette, including linked stylesheets.
 await page.route('**/static/style.css',async route=>route.fulfill({contentType:'text/css',body:recolor(await fs.readFile(path.join(root,'web/static/style.css'),'utf8'),p)}));
 await page.reload();
 const rgb=(p.art || p.brand).match(/\w\w/g).map(x=>parseInt(x,16)/255);
 const rows=rgb.map(c=>`${(1-c)/.75} 0 ${(c-1)/.75} 0 1`).join(' ');
 await page.evaluate(({rows})=>{
  document.body.insertAdjacentHTML('beforeend',`<svg width="0" height="0" style="position:absolute" aria-hidden="true"><filter id="preview-brand-art" color-interpolation-filters="sRGB"><feColorMatrix type="matrix" values="${rows} 0 0 0 1 0"/></filter></svg>`);
 },{rows});
 await page.addStyleTag({content:'.hero-art{filter:url(#preview-brand-art)}'});
 await page.evaluate(()=>document.fonts.ready);
 await page.screenshot({path:path.join(out,p.id+'.png'),fullPage:true});
 await page.setViewportSize({width:390,height:844});
 await page.screenshot({path:path.join(out,p.id+'-mobile.png'),fullPage:true});
 checks.push({palette:p.id,mobileOverflow:await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth)});
 await page.setViewportSize({width:1440,height:1050});
 await page.click('#preview');
 await page.evaluate(()=>{document.activeElement?.blur();window.scrollTo(0,0);});
 await page.screenshot({path:path.join(out,p.id+'-wynik.png'),fullPage:true});
 await page.unroute('**/static/style.css');
 await page.goto(`${origin}/extension/popup.html?palette=${p.id}`);
 await page.evaluate(()=>{document.querySelector('#st').textContent='Podgląd kolorystyki wtyczki • bez połączenia z serwerem';});
 await page.evaluate(()=>document.fonts.ready);
 await page.locator('body').screenshot({path:path.join(out,p.id+'-wtyczka.png')});
}
function lum(hex){return hex.match(/\w\w/g).map(x=>parseInt(x,16)/255).map(x=>x<=.04045?x/12.92:((x+.055)/1.055)**2.4).reduce((s,x,i)=>s+x*[.2126,.7152,.0722][i],0)}
for(const p of palettes){p.contrastWhite=Number((1.05/(lum(p.brand)+.05)).toFixed(2));p.contrastPaper=Number(((lum(p.paper)+.05)/(lum(p.brand)+.05)).toFixed(2));}
await fs.writeFile(path.join(out,'palettes.json'),JSON.stringify({palettes,checks},null,2));
const cards=palettes.map(p=>`<article><div class="label"><h2>${p.name}</h2><div class="swatches">${(reference ? ['#cab891','#70683b','#81231e','#5f6a54','#2b2c1e'] : [p.brand,p.deep,p.paper,p.soft]).map(c=>`<span><i style="background:${c}"></i>${c}</span>`).join('')}</div></div><a href="${p.id}.png"><img class="home" src="${p.id}.png" alt="Strona główna: ${p.name}"></a><p>${p.desc}</p><nav><a href="${p.id}.png">Pełny ekran ↗</a><a href="${p.id}-mobile.png">Telefon ↗</a><a href="${p.id}-wynik.png">Wynik ↗</a><a href="${p.id}-wtyczka.png">Wtyczka ↗</a></nav></article>`).join('');
await fs.writeFile(path.join(out,'index.html'),`<!doctype html><html lang="pl"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Prawdowid — wybór kolorystyki</title><style>*{box-sizing:border-box}body{margin:0;padding:40px;background:#e8e6df;color:#191919;font:16px/1.5 system-ui}header{margin-bottom:30px}h1{font-size:36px;margin:0 0 8px;letter-spacing:-1px}header p{margin:0;max-width:1100px}main{display:grid;grid-template-columns:repeat(${sea ? 1 : more || red || reference || carmine ? 3 : 2},1fr);gap:28px}article{background:#faf9f5;border:1px solid #aaa79d;padding:20px;min-width:0}h2{font-size:23px;margin:0 0 10px}.swatches{display:flex;gap:18px;font:12px monospace}.swatches span{display:flex;align-items:center;gap:7px}.swatches i{width:19px;height:19px;border:1px solid #aaa}.home{width:100%;display:block;border:1px solid #b8b5ab;margin-top:18px}article p{font-size:15px;margin:15px 0 10px;min-height:46px}nav{display:flex;gap:20px}a{color:inherit}footer{margin-top:22px;font-size:13px}@media(max-width:950px){body{padding:20px}main{grid-template-columns:1fr}.swatches{flex-wrap:wrap}nav{flex-wrap:wrap}}</style><header><h1>PRAWDOWID / ${carmine ? "Karmin / oryginał i pięć wariantów" : sea ? "wariant morski" : reference ? "Twoja paleta / trzy kompozycje" : red ? "sześć odcieni czerwieni" : more ? "sześć kolejnych propozycji" : "cztery kierunki kolorystyczne"}</h1><p>Podglądy istniejącego interfejsu. Ten sam układ, typografia i ilustracja — różne kolory marki, papieru i akcentów. Propozycje do wyboru; aplikacja pozostaje bez zmian.</p></header><main>${cards}</main><footer>Kolory werdyktów pozostają niezależne od marki: fałsz — czerwony; potwierdzenie — zielony; ostrzeżenie — bursztynowy. Podglądy wyników korzystają z jawnie fikcyjnego przykładu wbudowanego w aplikację.</footer></html>`);
await page.setViewportSize({width:sea ? 1440 : more || red || reference || carmine ? 2400 : 2000,height:reference || sea ? 1000 : 1700});
await page.goto('file://'+path.join(out,'index.html'));
await page.screenshot({path:path.join(out,'porownanie.png'),fullPage:true});
if (red || reference || carmine) {
 await page.evaluate(()=>{document.querySelector('h1').textContent='PRAWDOWID / kolor marki a werdykt'; for(const img of document.querySelectorAll('img.home')) img.src=img.src.replace('.png','-wynik.png');});
 await page.evaluate(()=>Promise.all([...document.images].map(img=>img.decode())));
 await page.screenshot({path:path.join(out,'porownanie-wynikow.png'),fullPage:true});
}
console.log(JSON.stringify({palettes:palettes.map(p=>({name:p.name,contrastWhite:p.contrastWhite,contrastPaper:p.contrastPaper})),checks}));
await browser.close();server.close();
