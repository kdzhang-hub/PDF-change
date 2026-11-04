const fs=require('fs'),path=require('path');
const {chromium}=require('C:/Users/35100/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const root=path.resolve(__dirname,'..'),pid=JSON.parse(fs.readFileSync(path.join(root,'work/manual-text-project.json'))).id;
(async()=>{
 const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
 try{
  const page=await browser.newPage({viewport:{width:1440,height:960}});
  await page.goto('http://127.0.0.1:8765');
  await page.locator('.project-list button').filter({hasText:'小标签手工校正验证'}).first().click();
  await page.locator('.layer-select').filter({hasText:'小标签图片'}).click();
  await page.getByRole('tab',{name:'属性',exact:true}).click();
  await page.getByRole('button',{name:'框选',exact:true}).click();
  const rect=await page.locator('.konvajs-content').boundingBox();
  const scale=Math.min((rect.width-96)/400,(rect.height-96)/200);
  const ox=rect.x+(rect.width-400*scale)/2,oy=rect.y+(rect.height-200*scale)/2;
  await page.mouse.move(ox+50.1*scale,oy+40.1*scale);await page.mouse.down();
  await page.mouse.move(ox+209.9*scale,oy+79.9*scale,{steps:6});await page.mouse.up();
  await page.locator('.manual-text summary').click();
  await page.getByLabel('手工校正文字',{exact:true}).fill('小标签已校正');
  await page.getByLabel('手工文字字号',{exact:true}).fill('6');
  await page.getByRole('button',{name:'清除原字并生成文本框',exact:true}).click();
  await page.getByText('处理完成，请检查需要校正的图层',{exact:true}).waitFor({timeout:30000});
  await page.getByRole('tab',{name:/^图层/}).click();
  await page.locator('.layer-select').filter({hasText:'小标签已校正'}).click();
  await page.getByRole('tab',{name:'属性',exact:true}).click();
  await page.getByLabel('字体',{exact:true}).fill('Arial');await page.getByLabel('字号',{exact:true}).fill('8');
  await page.getByText('已保存',{exact:true}).waitFor();
  const result=await (await page.request.get(`http://127.0.0.1:8765/api/projects/${pid}`)).json();
  const text=result.pages[0].layers.find(l=>l.kind==='text');
  if(text.text!=='小标签已校正'||text.font!=='Arial'||text.font_size!==8)throw new Error('Manual correction did not persist');
  const download=page.waitForEvent('download');await page.getByRole('button',{name:'导出 PPTX',exact:true}).click();
  await (await download).saveAs(path.join(root,'deliverables/manual-small-label.pptx'));
  await page.screenshot({path:path.join(root,'deliverables/ui-manual-small-label.png'),fullPage:true});
  fs.writeFileSync(path.join(root,'deliverables/manual-text-ui-test.json'),JSON.stringify({project:pid,boxSelection:true,manualCorrection:true,fontEdit:true,sizeEdit:true,export:true},null,2));
  console.log('Manual small-label browser flow passed');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exit(1)});
