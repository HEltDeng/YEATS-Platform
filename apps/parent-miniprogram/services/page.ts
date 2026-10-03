import {ApiError,request,login,token,clearSession,studentPath,activeStudent,setStudent,idempotency,upload,ticket,message,date} from './api';
import {config} from '../config';

const statusNames:any={todo:'待提交',submitted:'待批改',returned:'退回重做',graded:'已批改',present:'已签到',makeup:'补签',absent:'缺勤',leave:'请假',pending:'待审核',approved:'已通过',rejected:'已驳回',scheduled:'待上课',completed:'已完成',cancelled:'已取消'};
const fileNames:any={image:'图片',audio:'音频',video:'视频',word:'Word',pdf:'PDF',ppt:'PPT',excel:'Excel'};
const tabPages=['home','homework','knowledge','me'];
const routes:any={'hours':'我的课时','ledger':'课时消耗明细','attendance':'签到明细','schedule':'班级与课表','tests':'随堂测试','homework':'作业','homework-detail':'作业详情','feedback':'批改结果','recordings':'缺课与在线课程','knowledge':'班级知识库','knowledge-detail':'知识内容','teachers':'师资展示','teacher-detail':'老师详情','notifications':'通知中心','me':'我的','profile':'个人资料','settings':'设置','content':'叶芝英语','login':'家长登录','home':'叶芝英语'};
function decorate(items:any[]){return items.map(x=>({...x,statusText:statusNames[x.status]||x.status,date:date(x.created_at),due:date(x.due_at),start:date(x.starts_at),time:date(x.starts_at).slice(11),day:date(x.starts_at).slice(0,10),valid:date(x.valid_until),end:date(x.ends_at),arrived:date(x.arrived_at),expires:date(x.expires_at),lesson:x.lesson?{...x.lesson,start:date(x.lesson.starts_at)}:undefined}));}
export function registerPage(name:string){Page({
 data:{name,loading:false,error:'',busy:false,studentId:'',student:null,students:[],showStudents:false,showSupport:false,support:null,supportUrl:'',supportError:'',showApply:false,showQuestion:false,text:'',files:[],items:[],filtered:[],tab:'',query:'',data:null,detail:null,me:null,content:[],teachers:[],testMode:config.developmentLogin,consent:false,apiConfigured:!!config.apiBase,hasSession:false,showPhone:false,lessonId:'',profileName:'',categories:[],tree:[],expanded:[] as string[],selectedCategory:'',week:[],weekLabel:'',weekOffset:0,scheduleList:false,videoUrl:'',playbackSeconds:0,recordingId:'',filterStart:'',filterEnd:'',persona:'parent-a'},
 options:{} as Record<string,string>, epoch:0,visible:false,requestKey:'',lastWatch:0,externalFlow:false,resumePreserve:false,
 onLoad(options:Record<string,string>){this.options=options;wx.setNavigationBarTitle({title:routes[name]||'叶芝英语'});wx.hideShareMenu({menus:['shareAppMessage','shareTimeline']});},
 onShow(){this.visible=true;if(this.resumePreserve){this.resumePreserve=false;return;}this.load();},
 onHide(){this.visible=false;if(this.externalFlow){this.resumePreserve=true;return;}this.epoch++;this.setData({videoUrl:'',showApply:false,showQuestion:false,showStudents:false});},
 onUnload(){this.visible=false;this.epoch++;},
 onPullDownRefresh(){this.load().finally(()=>wx.stopPullDownRefresh());},
 async load(){const epoch=++this.epoch;this.setData({loading:true,error:'',data:null,detail:null,items:[],filtered:[],videoUrl:''});
  try{
   if(name==='login'){this.setData({hasSession:!!token()});if(token()){const m=await request('/v1/me');if(epoch!==this.epoch)return;this.setData({showPhone:m.needs_phone});if(!m.needs_phone){wx.switchTab({url:'/pages/home/index'});return;}}return;}
   if(name==='content'&&!token()){const c=await request('/v1/content?kind='+encodeURIComponent(this.options.kind||'introduction'));this.setIf(epoch,{data:c,items:c,loading:false});return;}
   if(!token()){wx.reLaunch({url:'/pages/login/index'});return;}
   const [m,students]=await Promise.all([request('/v1/me'),request('/v1/students')]);if(epoch!==this.epoch)return;
   if(m.needs_phone){wx.reLaunch({url:'/pages/login/index'});return;}
   let sid=activeStudent();if(!students.some((s:any)=>s.id===sid)){sid=students[0]?.id||'';setStudent(sid);}
   this.setData({me:m,students,studentId:sid,student:students.find((s:any)=>s.id===sid)||null,profileName:m.name});
   const publicPages=['me','profile','settings','content','teachers','teacher-detail'];
   if(!sid&&!publicPages.includes(name))return;
   let data:any;
   if(name==='home') {const [d,c]=await Promise.all([request(studentPath('/home',sid)),request('/v1/content')]);data=d;const banners=await Promise.all(c.filter((x:any)=>x.kind==='banner').map(async(x:any)=>({...x,imageUrl:x.files?.find((f:any)=>f.kind==='image')?(await ticket(x.files.find((f:any)=>f.kind==='image').id)).url:''})));this.setIf(epoch,{content:c,banners,announcements:c.filter((x:any)=>x.kind==='announcement')});data.homework=decorate(data.homework);}
   else if(name==='hours'||name==='ledger'){data=await request(studentPath('/hours',sid));data.entries=decorate(data.entries);data.packages=decorate(data.packages);data.progress=data.total?Math.min(100,Math.round(data.consumed/data.total*100)):0;}
   else if(name==='attendance'){data=decorate(await request(studentPath('/attendance',sid)));this.setIf(epoch,{counts:{present:data.filter((x:any)=>x.status==='present').length,makeup:data.filter((x:any)=>x.status==='makeup').length,absent:data.filter((x:any)=>x.status==='absent').length}});}
   else if(name==='schedule'){data=await request(studentPath('/schedule',sid));data.lessons=decorate(data.lessons);}
   else if(name==='tests'){data=decorate(await request(studentPath('/tests',sid)));}
   else if(name==='homework'){data=decorate(await request(studentPath('/homework',sid)));}
   else if(name==='homework-detail'||name==='feedback'){data=await request(studentPath('/homework/'+this.options.id,sid));data=decorate([data])[0];data.history=decorate(data.history);for(const h of data.history)h.feedback=decorate(h.feedback);this.setIf(epoch,{detail:data});}
   else if(name==='recordings'){data=await request(studentPath('/recordings',sid));data.absences=decorate(data.absences);data.requests=decorate(data.requests);data.grants=decorate(data.grants);}
   else if(name==='knowledge'){data=await request(studentPath('/knowledge?q='+encodeURIComponent(this.data.query),sid));data.items=data.items.map((k:any)=>({...k,pathText:k.path.join(' › '),files:k.files.map((f:any)=>({...f,label:fileNames[f.kind]||f.kind}))}));this.setIf(epoch,{categories:data.categories});}
   else if(name==='knowledge-detail'){data=await request(studentPath('/knowledge/'+this.options.id,sid));data.questions=decorate(data.questions);data.pathText=data.path.join(' › ');this.setIf(epoch,{detail:data});}
   else if(name==='teachers'||name==='teacher-detail'){data=await request('/v1/teachers');if(name==='teacher-detail'){data=data.find((x:any)=>x.id===this.options.id);if(!data)throw Error('老师信息已下架');this.setIf(epoch,{detail:data});}}
   else if(name==='notifications'){data=decorate(await request(studentPath('/notifications',sid)));}
   else if(name==='content'){data=await request('/v1/content?kind='+encodeURIComponent(this.options.kind||'introduction'));if(this.options.id)data=data.filter((x:any)=>x.id===this.options.id);}
   if(epoch!==this.epoch)return;this.setData({data,items:Array.isArray(data)?data:[],loading:false});this.filter();if(name==='schedule')this.buildWeek();if(name==='knowledge')this.buildTree();
  }catch(e){if(epoch===this.epoch){this.setData({error:message(e)});if(e instanceof ApiError&&e.status===401)wx.reLaunch({url:'/pages/login/index'});}}finally{if(epoch===this.epoch)this.setData({loading:false});}
 },
 setIf(epoch:number,value:any){if(epoch===this.epoch&&this.visible)this.setData(value);},
 go(e:any){this.navigate(e.currentTarget.dataset.page,e.currentTarget.dataset.id,e.currentTarget.dataset.kind);},
 navigate(page:string,id?:string,kind?:string){if(!routes[page])return;const url='/pages/'+page+'/index'+(id?'?id='+encodeURIComponent(id):kind?'?kind='+encodeURIComponent(kind):'');if(tabPages.includes(page))wx.switchTab({url});else wx.navigateTo({url});},
 input(e:any){this.setData({[e.currentTarget.dataset.field||'text']:e.detail.value});},
 toggleConsent(){this.setData({consent:!this.data.consent});},
 async wechatLogin(){if(!this.data.consent){this.setData({error:'请先阅读并同意用户协议和隐私政策'});return;}await this.action(async()=>{const d=await login();this.setData({hasSession:true,showPhone:d.needs_phone});if(!d.needs_phone)wx.switchTab({url:'/pages/home/index'});});},
 async phone(e:any){if(!e.detail.code){this.setData({error:'未授权手机号，暂无法关联学员'});return;}await this.action(async()=>{await request('/v1/auth/phone','POST',{code:e.detail.code});wx.switchTab({url:'/pages/home/index'});});},
 async developmentLogin(e:any){if(!config.developmentLogin||config.environment!=='development')return;await this.action(async()=>{const r=await request('/v1/auth/development/'+(e.currentTarget.dataset.persona||'parent-a'),'POST');wx.setStorageSync('yeats.session',r.token);setStudent('');wx.switchTab({url:'/pages/home/index'});});},
 async action(fn:()=>Promise<any>){if(this.data.busy)return;this.setData({busy:true,error:''});try{await fn();}catch(e){this.setData({error:message(e)});if(e instanceof ApiError&&e.status===401)wx.reLaunch({url:'/pages/login/index'});}finally{this.setData({busy:false});}},
 openStudents(){this.setData({showStudents:true});},closeStudents(){this.setData({showStudents:false});},
 async chooseStudent(e:any){const sid=e.currentTarget.dataset.id;this.epoch++;setStudent(sid);this.setData({showStudents:false,studentId:sid,student:null,data:null,detail:null,items:[],filtered:[],files:[],text:'',videoUrl:'',expanded:[],selectedCategory:''});if(['homework-detail','feedback','knowledge-detail'].includes(name)){wx.navigateBack();return;}await this.load();},
 tabChange(e:any){this.setData({tab:e.currentTarget.dataset.tab});this.filter();},
 filter(){let filtered=this.data.items;const t=this.data.tab;if(name==='homework'){filtered=filtered.filter((x:any)=>!t||t==='todo'&&['todo','returned'].includes(x.status)||t===x.status);}else if(name==='tests'){filtered=filtered.filter((x:any)=>!t||t===x.kind);}else if(name==='notifications'){filtered=filtered.filter((x:any)=>!t||(t==='homework'?['homework','feedback'].includes(x.kind):['recording','course'].includes(x.kind)));}else if(name==='attendance'&&t)filtered=filtered.filter((x:any)=>x.status===t);this.setData({filtered});},
 async selectPictures(){this.externalFlow=true;try{const sid=this.data.studentId;const epoch=this.epoch;const detail:any=this.data.detail;const count=detail?.limits?.image_count||0;await this.action(async()=>{const room=count-this.data.files.length;if(room<=0)throw Error('已达到本次上传张数上限');const choice=await wx.chooseMedia({count:room,mediaType:['image'],sourceType:['album','camera']});let files:any[]=[...this.data.files];for(const f of choice.tempFiles){if(f.size>detail.limits.image_bytes)throw Error('图片超过单张大小上限');const saved=await upload(f.tempFilePath,sid);files.push({...saved,local:f.tempFilePath});if(epoch===this.epoch)this.setData({files});}});}finally{this.externalFlow=false;}},
 removePicture(e:any){this.setData({files:this.data.files.filter((x:any)=>x.id!==e.currentTarget.dataset.id)});},
 previewPicture(e:any){wx.previewImage({urls:this.data.files.map((f:any)=>f.local),current:e.currentTarget.dataset.url});},
 async submitHomework(){await this.action(async()=>{if(!this.requestKey)this.requestKey=idempotency();await request(studentPath('/homework/'+this.options.id+'/submissions'),'POST',{text:this.data.text,attachment_ids:this.data.files.map((x:any)=>x.id),idempotency_key:this.requestKey});this.requestKey='';this.setData({text:'',files:[]});await this.load();wx.showToast({title:'作业已保存',icon:'success'});});},
 async support(){this.setData({showSupport:true,supportError:'',supportUrl:''});try{const c=await request('/v1/content?kind=support');const s=c[0];this.setData({support:s||null});if(s?.files?.[0]){const t=await ticket(s.files[0].id);this.setData({supportUrl:t.url});}}catch(e){this.setData({supportError:message(e)});}},closeSupport(){this.setData({showSupport:false});},
 applyOpen(e:any){this.setData({showApply:true,lessonId:e.currentTarget.dataset.id,text:''});this.requestKey=idempotency();},closeApply(){this.setData({showApply:false});},
 async submitApply(){await this.action(async()=>{await request(studentPath('/lessons/'+this.data.lessonId+'/viewing-requests'),'POST',{reason:this.data.text,idempotency_key:this.requestKey});this.setData({showApply:false});this.requestKey='';await this.load();});},
 askOpen(){this.setData({showQuestion:true,text:''});this.requestKey=idempotency();},closeQuestion(){this.setData({showQuestion:false});},
 async submitQuestion(){await this.action(async()=>{await request(studentPath('/knowledge/'+this.options.id+'/questions'),'POST',{text:this.data.text,idempotency_key:this.requestKey});this.setData({showQuestion:false});this.requestKey='';await this.load();});},
 async search(){await this.load();},
 buildTree(){const d:any=this.data.data;if(!d)return;const expanded=this.data.expanded;let tree:any[]=[];const visit=(parent:string|null)=>{for(const c of d.categories.filter((x:any)=>x.parent_id===parent).sort((a:any,b:any)=>a.sort-b.sort)){tree.push({...c,indent:(c.level-1)*20,open:expanded.includes(c.id),leaf:false});if(expanded.includes(c.id)){visit(c.id);if(c.level===7)for(const k of d.items.filter((x:any)=>x.category_id===c.id))tree.push({...k,level:8,indent:140,leaf:true,name:k.title});}}};visit(null);this.setData({tree,filteredKnowledge:d.items});},
 toggleCategory(e:any){const id=e.currentTarget.dataset.id;const expanded=this.data.expanded.includes(id)?this.data.expanded.filter((x:string)=>x!==id):[...this.data.expanded,id];this.setData({expanded});this.buildTree();},
 expandAll(){this.setData({expanded:this.data.categories.map((c:any)=>c.id)});this.buildTree();},collapseAll(){this.setData({expanded:[]});this.buildTree();},
 async playRecording(e:any){await this.action(async()=>{const t=await ticket(e.currentTarget.dataset.file,'play');this.setData({videoUrl:t.url,recordingId:e.currentTarget.dataset.id});this.lastWatch=0;});},
 async watchTime(e:any){const seconds=Math.floor(e.detail.currentTime);this.setData({playbackSeconds:seconds});if(seconds-this.lastWatch>=30){this.lastWatch=seconds;try{await request(studentPath('/recordings/'+this.data.recordingId+'/watch'),'POST',{seconds:30});}catch(e){this.setData({videoUrl:'',error:message(e)});}}},
 videoError(){this.setData({videoUrl:'',error:'视频无法播放，请重试；权限到期后需重新申请'});},
 async readAll(){await this.action(async()=>{await request(studentPath('/notifications/read'),'POST');await this.load();});},
 async openNotice(e:any){const n=e.currentTarget.dataset.item;await this.action(async()=>{await request(studentPath('/notifications/'+n.id+'/read'),'POST');const route=n.kind==='homework'?'homework-detail':n.kind==='feedback'?'feedback':n.kind==='test'?'tests':n.kind==='knowledge'?'knowledge-detail':'recordings';if(n.resource_id)this.navigate(route,n.resource_id);else this.navigate(route);});},
 async saveProfile(){await this.action(async()=>{await request('/v1/me','PUT',{name:this.data.profileName});await this.load();wx.showToast({title:'资料已保存'});});},
 async subscriptions(){await this.action(async()=>{const me:any=this.data.me;if(!me.subscription_templates.length)throw Error('机构尚未配置微信订阅消息，站内通知仍可正常查看');const r=await wx.requestSubscribeMessage({tmplIds:me.subscription_templates.slice(0,3)});const choices:any={};for(const id of me.subscription_templates.slice(0,3))choices[id]=r[id];await request('/v1/me/subscriptions','POST',{choices});});},
 async logout(){await this.action(async()=>{await request('/v1/auth/logout','POST');clearSession();wx.reLaunch({url:'/pages/login/index'});});},
 weekMove(e:any){this.setData({weekOffset:this.data.weekOffset+Number(e.currentTarget.dataset.delta)});this.buildWeek();},
 buildWeek(){const d:any=this.data.data;if(!d)return;const now=new Date();now.setHours(0,0,0,0);now.setDate(now.getDate()-(now.getDay()+6)%7+this.data.weekOffset*7);const monday=now.getTime();const week=['一','二','三','四','五','六','日'].map((label,i)=>{const day=new Date(monday+i*86400000);const key=day.getFullYear()+'-'+String(day.getMonth()+1).padStart(2,'0')+'-'+String(day.getDate()).padStart(2,'0');return{label,date:day.getDate(),lessons:d.lessons.filter((l:any)=>l.day===key)};});this.setData({week,weekLabel:(now.getMonth()+1)+'月'+now.getDate()+'日起'});},
 toggleSchedule(){this.setData({scheduleList:!this.data.scheduleList});},
 filterDates(e:any){this.setData({[e.currentTarget.dataset.field]:e.detail.value});const d:any=this.data.data;this.setData({ledgerEntries:d.entries.filter((x:any)=>{const date=x.lesson?.start?.slice(0,10)||x.date.slice(0,10);return(!this.data.filterStart||date>=this.data.filterStart)&&(!this.data.filterEnd||date<=this.data.filterEnd);})});}
});}
