const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {chromium}=require('../frontend/node_modules/playwright');
const root=path.resolve(__dirname,'..'),out=path.join(root,'deliverables/logo-policy-20261031/ui');fs.mkdirSync(out,{recursive:true});
(async()=>{
 const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
 try{
  const page=await browser.newPage({viewport:{width:1440,height:960}}),errors=[];
  page.on('pageerror',e=>errors.push(String(e)));
  await page.goto('http://127.0.0.1:8765/');
  const {id}=JSON.parse(fs.readFileSync(path.join(root,'deliverables/logo-policy-20261031/fresh-project.json')));
  const base='http://127.0.0.1:8765/api/projects/'+id;
  const before=await (await page.request.get(base)).json();
  const mark=before.pages[0].layers.find(l=>l.content_role==='logo');assert(mark);
  await page.getByLabel('搜索本地项目',{exact:true}).fill(before.name);
  await page.locator('.project-list button').first().click();
  async function select(name){
   await page.getByRole('tab',{name:/^图层/}).click();
   await page.getByLabel('搜索图层与文字',{exact:true}).fill(name);
   await page.locator('.layer-select').filter({has:page.getByText(name,{exact:true})}).click();
   await page.getByRole('tab',{name:'属性',exact:true}).click();
  }
  async function role(button){
   const event=page.waitForResponse(r=>r.url().endsWith('/image-role')&&r.request().method()==='POST');
   await page.getByRole('button',{name:button,exact:true}).click();const r=await event;assert(r.ok());
   await page.getByRole('button',{name:'收起',exact:true}).waitFor({timeout:30000});
   await select(mark.name);
  }
  await select(mark.name);
  await page.waitForLoadState('networkidle');
  assert(await page.getByRole('button',{name:'保留完整标识',exact:true}).isDisabled());
  assert.equal(await page.getByRole('button',{name:'本地识别此素材中的文字',exact:true}).count(),0);
  await page.screenshot({path:path.join(out,'preserved-mark.png')});
  await role('作为普通素材处理');
  await page.getByRole('button',{name:'本地识别此素材中的文字',exact:true}).waitFor();
  await role('保留完整标识');
  assert.equal(await page.getByRole('button',{name:'本地识别此素材中的文字',exact:true}).count(),0);
  const label=before.pages[0].layers.find(l=>l.kind==='text'&&l.text==='参赛赛道');assert(label);
  await select(label.name);
  await page.getByLabel('文字内容',{exact:true}).fill('普通小标签验证');
  await page.getByLabel('字体',{exact:true}).fill('Arial');
  await page.getByLabel('字号',{exact:true}).fill('6');
  await page.getByText('已保存',{exact:true}).waitFor();
  for(let i=0;i<3;i++)await page.getByRole('button',{name:'撤销 Ctrl+Z',exact:true}).click();
  await page.getByText('已保存',{exact:true}).waitFor();
  const after=await (await page.request.get(base)).json(),preserved=after.pages[0].layers.find(l=>l.id===mark.id),restored=after.pages[0].layers.find(l=>l.id===label.id);
  assert.equal(preserved.content_role,'logo');assert.equal(preserved.asset,mark.asset);
  for(const key of ['text','font','font_size','x','y','width','height'])assert.equal(restored[key],label[key]);
  assert.deepEqual(errors,[]);
  await select(mark.name);await page.screenshot({path:path.join(out,'restored-mark-controls.png')});
  fs.writeFileSync(path.join(out,'validation.json'),JSON.stringify({project:id,automaticLogo:true,roleSwitch:true,ocrHiddenForLogo:true,ordinaryTextFontSizeEditUndo:true,originalLogoAssetUnchanged:true,errors},null,2));
  console.log('Logo policy and ordinary text editing UI passed.');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
