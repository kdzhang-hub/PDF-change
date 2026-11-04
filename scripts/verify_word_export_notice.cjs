// Read-only real-project flow: select one page, export DOCX, inspect its notice.
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {chromium}=require('../frontend/node_modules/playwright');
const root=path.resolve(__dirname,'..'),out=path.join(root,'deliverables/word-effects-20261030/web-notice');
fs.mkdirSync(out,{recursive:true});
(async()=>{
 const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
 try{
  const page=await browser.newPage({viewport:{width:1440,height:960}}),errors=[];
  page.on('pageerror',e=>errors.push(String(e)));
  await page.goto('http://127.0.0.1:8765/');
  const id='0260171f3114407b997bef2c370a4c62',base='http://127.0.0.1:8765/api/projects/'+id;
  const before=await (await page.request.get(base)).json();
  const query=before.name.toLocaleLowerCase();
  const list=await (await page.request.get('http://127.0.0.1:8765/api/projects')).json();
  const index=list.filter(p=>p.name.toLocaleLowerCase().includes(query)).findIndex(p=>p.id===id);assert(index>=0);
  await page.getByLabel('搜索本地项目',{exact:true}).fill(query);
  await page.locator('.project-list button').nth(index).click();
  await page.getByRole('button',{name:'取消全选',exact:true}).click();
  // Page 9 contains two measured groups rejected by the conservative fit gate.
  await page.getByLabel('选择第 9 页',{exact:true}).check();
  await page.getByRole('img',{name:'第 9 页原稿',exact:true}).click();
  await page.getByLabel('导出格式',{exact:true}).selectOption('docx');
  const download=page.waitForEvent('download');
  await page.getByRole('button',{name:'导出 Word',exact:true}).click();
  await (await download).saveAs(path.join(out,'page-9.docx'));
  await page.locator('.notice').filter({hasText:'部分艺术字的字形测量不可靠'}).waitFor();
  const notice=await page.locator('.notice').innerText();
  await page.screenshot({path:path.join(out,'export-notice.png')});
  const after=await (await page.request.get(base)).json();assert.deepEqual(before.pages,after.pages);assert.deepEqual(errors,[]);
  const health=await (await page.request.get('http://127.0.0.1:8765/api/health')).json();assert.equal(health.budget.calls.length,0);
  fs.writeFileSync(path.join(out,'validation.json'),JSON.stringify({notice,savedScenesUnchanged:true,page:9,download:true,errors,cloudCalls:health.budget.calls.length},null,2));
  console.log(JSON.stringify({ok:true,notice}));
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
