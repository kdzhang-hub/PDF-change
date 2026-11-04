// Real browser checks against an isolated imported project. Never edit user projects.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {chromium}=require('../frontend/node_modules/playwright');
const root=path.resolve(__dirname,'..');
const out=path.join(root,'deliverables','studio-refinement-20261030');
fs.mkdirSync(out,{recursive:true});
const errors=[],external=[],checks={};
(async()=>{
 const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
 try{
  const page=await browser.newPage({viewport:{width:1440,height:960},deviceScaleFactor:1});
  page.on('pageerror',e=>errors.push(String(e)));
  page.on('request',r=>{if(!r.url().startsWith('http://127.0.0.1:8765/')&&!/^(data:|blob:)/.test(r.url()))external.push(r.url())});
  await page.goto('http://127.0.0.1:8765/');
  await page.locator('.upload-card').waitFor();
  await page.screenshot({path:path.join(out,'home-desktop.png'),fullPage:true});
  if(process.argv[2]==='--resume-project'){
   const list=await (await page.request.get('http://127.0.0.1:8765/api/projects')).json();
   assert.equal(list[0].id,process.argv[3],'Only resume the known latest isolated QA project');
   await page.locator('.project-list button').first().click();
  }else{
   await page.locator('input[type=file]').setInputFiles(path.join(root,'samples','digital.pdf'));
   await page.getByRole('button',{name:'自动还原 2 页',exact:true}).waitFor();
   await page.getByRole('button',{name:'自动还原 2 页',exact:true}).click();
   await page.getByText('处理完成，请检查需要校正的图层',{exact:true}).waitFor({timeout:180000});
  }
  const state=await page.request.get('http://127.0.0.1:8765/api/projects');
  checks.projectId=(await state.json())[0].id;
  await page.getByRole('group',{name:'图层筛选'}).getByRole('button',{name:'文字',exact:true}).click();
  await page.locator('.layer-select').filter({hasText:'收入 128.50 万元'}).click();
  await page.locator('.edit-selected').click();
  await page.getByLabel('文字内容',{exact:true}).waitFor();
  assert.equal(await page.getByRole('tab',{name:'属性',exact:true}).getAttribute('aria-selected'),'true');
  assert.equal(await page.locator('#layers-panel').isVisible(),false);
  await page.locator('#text-edit').fill('收入 999.00 万元');
  await page.getByText('已保存',{exact:true}).waitFor();
  await page.getByRole('button',{name:'撤销 Ctrl+Z',exact:true}).click();
  await page.waitForFunction(()=>document.querySelector('#text-edit')?.value==='收入 128.50 万元');
  await page.getByLabel('字体',{exact:true}).fill('Microsoft YaHei');
  await page.getByLabel('字号',{exact:true}).fill('6');
  const boldButton=page.getByRole('button',{name:'粗体',exact:true});
  if(await boldButton.getAttribute('aria-pressed')!=='true')await boldButton.click();
  await page.getByText('已保存',{exact:true}).waitFor();
  const edited=(await (await page.request.get(`http://127.0.0.1:8765/api/projects/${checks.projectId}`)).json()).pages[0].layers.find(l=>l.kind==='text'&&l.text==='收入 128.50 万元');
  assert(edited);assert.equal(edited.font,'Microsoft YaHei');assert.equal(edited.font_size,6);assert.equal(edited.bold,true);
  checks.editing={text:true,undo:true,font:true,size:6,bold:true,persisted:true};
  await page.screenshot({path:path.join(out,'editor-properties.png')});
  await page.getByText('位置与尺寸',{exact:true}).click();
  assert(await page.getByLabel('X',{exact:true}).isVisible());
  await page.getByText('位置与尺寸',{exact:true}).click();
  // ARIA tabs support roving keyboard focus and retain selections.
  await page.getByRole('tab',{name:'属性',exact:true}).focus();
  await page.keyboard.press('ArrowLeft');
  assert.equal(await page.getByRole('tab',{name:/^图层/}).getAttribute('aria-selected'),'true');
  await page.getByLabel('搜索图层与文字',{exact:true}).fill('收入');
  assert.equal(await page.locator('.layer-select').count(),1);
  await page.screenshot({path:path.join(out,'editor-layers.png')});
  await page.getByRole('tab',{name:/^图层/}).focus();
  await page.keyboard.press('End');
  assert.equal(await page.getByRole('tab',{name:'属性',exact:true}).getAttribute('aria-selected'),'true');
  checks.keyboardTabs=true;
  const sceneBeforeViews=(await (await page.request.get(`http://127.0.0.1:8765/api/projects/${checks.projectId}`)).json()).pages;
  checks.layouts=[];
  for(const [width,height] of [[1440,960],[1024,768],[375,812],[812,375]]){
   await page.setViewportSize({width,height});
   if(width<=760)await page.getByRole('button',{name:'画布',exact:true}).click();
   const before=await page.locator('.viewport').boundingBox();
   await page.getByRole('button',{name:'专注画布',exact:true}).click();
   await page.waitForFunction(()=>document.querySelector('.viewport').clientWidth>0);
   const focused=await page.locator('.viewport').boundingBox();
   assert(focused.height>=before.height,JSON.stringify({width,before,focused}));
   assert(focused.width>=before.width,JSON.stringify({width,before,focused}));
   const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth);
   assert.equal(overflow,false);
   await page.screenshot({path:path.join(out,`focus-${width}x${height}.png`)});
   // Escape must restore normal editing without losing selection.
   await page.locator('.focus-canvas').focus();
   await page.keyboard.press('Escape');
   assert.equal(await page.locator('.focused-canvas').count(),0);
   if(width<=760){
    await page.getByRole('button',{name:'字体与图层',exact:true}).click();
    assert(await page.getByLabel('字号',{exact:true}).isVisible());
    const fontBox=await page.getByLabel('字号',{exact:true}).boundingBox();
    assert(fontBox.y+fontBox.height<=height-28,'Font size should be reachable without scrolling in the mobile property view');
    await page.screenshot({path:path.join(out,'editor-mobile-properties.png')});
    await page.getByRole('button',{name:'画布',exact:true}).click();
   }
   checks.layouts.push({width,height,overflow,before,focused});
  }
  const sceneAfterViews=(await (await page.request.get(`http://127.0.0.1:8765/api/projects/${checks.projectId}`)).json()).pages;
  assert.deepEqual(sceneAfterViews,sceneBeforeViews);
  checks.viewOnlySceneUnchanged=true;
  await page.setViewportSize({width:1440,height:960});
  await page.emulateMedia({reducedMotion:'reduce'});
  checks.reducedMotion=await page.evaluate(()=>matchMedia('(prefers-reduced-motion: reduce)').matches);
  for(const format of ['pptx','docx']){
   await page.getByLabel('导出格式',{exact:true}).selectOption(format);
   const downloadEvent=page.waitForEvent('download');
   await page.getByRole('button',{name:format==='pptx'?'导出 PPTX':'导出 Word',exact:true}).click();
   const download=await downloadEvent;
   await download.saveAs(path.join(out,`browser-export.${format}`));
   checks[format]=!await download.failure();
  }
  await page.getByRole('button',{name:'返回项目',exact:true}).click();
  await page.setViewportSize({width:375,height:812});
  await page.screenshot({path:path.join(out,'home-mobile.png'),fullPage:true});
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
  assert.deepEqual(errors,[]);assert.deepEqual(external,[]);
  fs.writeFileSync(path.join(out,'validation.json'),JSON.stringify({checks,errors,externalRequests:external},null,2));
  console.log(JSON.stringify({ok:true,out,checks}));
 }finally{await browser.close()}
})().catch(e=>{fs.writeFileSync(path.join(out,'failure.json'),JSON.stringify({error:String(e),errors,checks},null,2));console.error(e);process.exitCode=1});
