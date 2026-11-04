// Render independent PDF paint groups with Chromium's SVG mask/clip support.
// Only MuPDF-generated SVG is accepted; all network requests are blocked.
const fs=require('fs');const path=require('path');
let pw;try{pw=require('../frontend/node_modules/playwright')}catch{pw=require('C:/Users/35100/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright')}
const [input,folder,prefix]=process.argv.slice(2);
(async()=>{
 const browser=await pw.chromium.launch({executablePath:process.env.LAYERDECK_CHROME||'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
 try{
 const page=await browser.newPage({viewport:{width:1440,height:810},deviceScaleFactor:1});
 await page.route('**/*',route=>route.request().url().startsWith('data:')?route.continue():route.abort());
 const source=fs.readFileSync(input,'utf8');
 if(/<script|<foreignObject|https?:\/\//i.test(source.replace(/xmlns(?::[\w-]+)?="[^"]*"/g,'')))throw new Error('Unsupported active or remote SVG content');
 await page.setContent('<!doctype html><style>html,body{margin:0;background:transparent}svg{display:block}</style>'+source);
 const meta=await page.evaluate(()=>{
  const svg=document.querySelector('svg');const w=svg.viewBox.baseVal.width,h=svg.viewBox.baseVal.height;const scale=1.5;
  svg.style.width=w*scale+'px';svg.style.height=h*scale+'px';
  const nodes=[];
  function collect(parent){
   for(const child of parent.children){
    if(['defs','metadata','title','desc','clipPath','mask','pattern'].includes(child.localName))continue;
    if(child.localName==='g')collect(child);
    else if(['image','path','text','use','rect','circle','ellipse','polygon','polyline','line'].includes(child.localName))nodes.push(child);
   }
  }
  collect(svg);const result=[];
  nodes.forEach((e,index)=>{
   e.setAttribute('data-layer-index',String(index));
   const box=e.getBoundingClientRect();
   const x=Math.max(0,Math.floor(box.x-2)),y=Math.max(0,Math.floor(box.y-2));
   const right=Math.min(Math.ceil(w*scale),Math.ceil(box.right+2)),bottom=Math.min(Math.ceil(h*scale),Math.ceil(box.bottom+2));
   const textNodes=e.localName==='text'?[e]:Array.from(e.querySelectorAll('text'));
   const texts=textNodes.map(t=>({text:t.textContent,font:t.getAttribute('font-family'),size:Number(t.getAttribute('font-size')),bold:t.getAttribute('font-weight')==='bold'}));
   result.push({index,x:x/scale,y:y/scale,width:(right-x)/scale,height:(bottom-y)/scale,clip:{x,y,width:right-x,height:bottom-y},tag:e.localName,texts});
   e.style.visibility='hidden';
  });
  return {width:w,height:h,scale,layers:result};
 });
 await page.setViewportSize({width:Math.ceil(meta.width*meta.scale),height:Math.ceil(meta.height*meta.scale)});
 fs.mkdirSync(folder,{recursive:true});
 for(const layer of meta.layers){
  if(layer.clip.width<1||layer.clip.height<1)continue;
  if(layer.texts.length&&layer.tag==='text')continue;
  await page.evaluate(index=>{document.querySelector(`[data-layer-index="${index}"]`).style.visibility='visible'},layer.index);
  layer.asset=`${prefix}-${layer.index}.png`;
  await page.screenshot({path:path.join(folder,layer.asset),clip:layer.clip,omitBackground:true,animations:'disabled'});
  await page.evaluate(index=>{document.querySelector(`[data-layer-index="${index}"]`).style.visibility='hidden'},layer.index);
 }
 fs.writeFileSync(path.join(folder,prefix+'.json'),JSON.stringify(meta));
 await page.evaluate(()=>document.querySelectorAll('[data-layer-index]').forEach(e=>e.style.visibility='visible'));
 await page.screenshot({path:path.join(folder,prefix+'-reference.png'),omitBackground:true,animations:'disabled'});
 console.log(JSON.stringify({layers:meta.layers.length,width:meta.width,height:meta.height}));
 }finally{await browser.close()}
})().catch(e=>{console.error(String(e));process.exit(1)});
