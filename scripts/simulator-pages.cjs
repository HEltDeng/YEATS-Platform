// Actual WeChat simulator routes, no wx mocks and no fabricated page state.
const automator=require('miniprogram-automator');
const fs=require('fs'),path=require('path');
const output=path.resolve(__dirname,'../../02_Deliverables-交付与验收/simulator');
(async()=>{
 const mini=await automator.connect({wsEndpoint:'ws://127.0.0.1:9420'});
 const records=[];
 try{
  for(const route of process.argv.slice(2)){
   const [name,query]=route.split('?');
   const page=await mini.reLaunch('/pages/'+name+'/index'+(query?'?'+query:''));
   for(let i=0;i<25;i++){await page.waitFor(200);if(!(await page.data('loading')))break;}
   const record={route,actual:(await mini.currentPage()).path,error:await page.data('error'),studentId:await page.data('studentId')};
   await mini.screenshot({path:path.join(output,name+'.png')});records.push(record);console.log(JSON.stringify(record));
  }
  fs.writeFileSync(path.join(output,'pages-'+Date.now()+'.json'),JSON.stringify(records,null,2));
 }finally{mini.disconnect();}
})().catch(()=>{console.error('Simulator operation failed; inspect current page. No private payload logged.');process.exitCode=1;});
