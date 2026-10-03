const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs'),path=require('node:path');
function api(wx){const ctx={exports:{},wx,require:()=>({config:{apiBase:'http://127.0.0.1:8930'}})};vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../services/api.js'),'utf8'),ctx);return ctx.exports;}
test('HTTP errors remain distinct and 401 clears the session',async()=>{
 for(const [status,fragment] of [[401,'登录已过期'],[403,'暂无操作权限'],[404,'不存在或无权访问'],[500,'服务器暂时异常']]){
  const removed=[];const a=api({getStorageSync:()=>'',removeStorageSync:k=>removed.push(k),request:o=>o.success({statusCode:status,data:{detail:'private internal detail'}})});
  await assert.rejects(a.request('/v1/me'),e=>e.status===status&&e.message.includes(fragment)&&!e.message.includes('private'));
  assert.equal(removed.length,status===401?2:0);
 }
});
test('connection refusal, timeout and recovery are handled separately',async()=>{
 let mode='refused';const a=api({getStorageSync:()=>'',request:o=>mode==='ok'?o.success({statusCode:200,data:{ok:true}}):o.fail({errMsg:mode==='timeout'?'request:fail timeout':'request:fail ECONNREFUSED'})});
 await assert.rejects(a.request('/health'),e=>e.status===0&&e.message.includes('无法连接服务'));
 mode='timeout';await assert.rejects(a.request('/health'),e=>e.message.includes('请求超时'));
 mode='ok';assert.equal((await a.request('/health')).ok,true);
});
test('refresh retains homework draft and failed retry keeps idempotency key',async()=>{
 let definition;const ctx={exports:{},Page:p=>definition=p,wx:{},require:id=>id==='../config'?{config:{}}:{token:()=>'',request:async()=>{throw Error('offline')},activeStudent:()=>'',message:e=>e.message,ApiError:Error}};
 vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../services/page.js'),'utf8'),ctx);ctx.exports.registerPage('homework-detail');
 const page=Object.assign({},definition,{data:{...definition.data,text:'未提交草稿',files:[{id:'retained'}]},setData(d){Object.assign(this.data,d)}});
 ctx.wx.reLaunch=()=>{};await page.load();assert.equal(page.data.text,'未提交草稿');assert.equal(page.data.files.length,1);
 let calls=0;page.data.busy=true;await page.action(async()=>calls++);assert.equal(calls,0);
});
