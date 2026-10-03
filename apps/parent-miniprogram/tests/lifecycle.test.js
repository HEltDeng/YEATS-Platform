const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs'),path=require('node:path');
const base=path.join(__dirname,'..');
function load(file,deps,extra={}){const context={exports:{},require:id=>deps[id],...extra};vm.runInNewContext(fs.readFileSync(path.join(base,file),'utf8'),context);return context.exports;}
test('UTC instants render China time, including next-day rollover',()=>{
 const api=load('services/api.js',{'../config':{config:{}}});
 assert.equal(api.date('2026-10-03T18:30:00Z'),'2026-10-04 02:30');
 assert.equal(api.date('2026-10-03T02:55:00'),'2026-10-03 10:55');
 assert.equal(api.date('2026-10-03'),'2026-10-03');
});
test('native image picker hide/show does not discard uploaded attachment',async()=>{
 let definition,resolvePicker,requests=0;
 const exports=load('services/page.js',{'../config':{config:{developmentLogin:true}},'./api':{message:e=>e.message,upload:async()=>({id:'unit-file'}),request:async()=>{requests++;return []}}},{Page:p=>definition=p,wx:{chooseMedia:()=>new Promise(r=>resolvePicker=r)}});
 exports.registerPage('homework-detail');
 const page=Object.assign({},definition,{data:{...definition.data,studentId:'unit-student',files:[],detail:{limits:{image_count:9,image_bytes:10485760}}},setData(d){Object.assign(this.data,d)}});
 page.visible=true;
 const upload=page.selectPictures();page.onHide();page.onShow();
 resolvePicker({tempFiles:[{tempFilePath:'synthetic-unit-image',size:100}]});await upload;
 assert.equal(page.data.files.length,1);assert.equal(page.data.files[0].id,'unit-file');assert.equal(requests,0);assert.equal(page.data.busy,false);
});
