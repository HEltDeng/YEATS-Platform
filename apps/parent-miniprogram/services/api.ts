import { config } from '../config';
export class ApiError extends Error { constructor(public status:number,message:string){super(message);} }
export function token():string{return wx.getStorageSync('yeats.session')||'';}
export function clearSession(){wx.removeStorageSync('yeats.session');wx.removeStorageSync('yeats.student');}
export function request<T=any>(path:string,method:WechatMiniprogram.RequestOption['method']='GET',data?:any):Promise<T>{
  if(!config.apiBase) return Promise.reject(new ApiError(503,'服务地址尚未配置，请联系机构'));
  return new Promise((resolve,reject)=>wx.request({url:config.apiBase+path,method,data,timeout:15000,header:{Authorization:'Bearer '+token(),'Content-Type':'application/json'},
    success:r=>{if(r.statusCode>=200&&r.statusCode<300)resolve(r.data as T);else{const d=r.data as any;if(r.statusCode===401)clearSession();reject(new ApiError(r.statusCode,typeof d.detail==='string'?d.detail:'请求未完成，请检查内容后重试'));}},
    fail:()=>reject(new ApiError(0,'网络连接失败，请检查网络后重试'))}));
}
export async function login(){const r=await wx.login();const out=await request('/v1/auth/wechat','POST',{code:r.code});wx.setStorageSync('yeats.session',out.token);return out;}
export function activeStudent():string{return wx.getStorageSync('yeats.student')||'';}
export function setStudent(id:string){wx.setStorageSync('yeats.student',id);}
export function studentPath(suffix:string,sid=activeStudent()){if(!sid)throw new ApiError(409,'请先选择学员');return '/v1/students/'+encodeURIComponent(sid)+suffix;}
export function idempotency(){return 'yeats-'+Date.now().toString(36)+'-'+Math.random().toString(36).slice(2)+'-'+Math.random().toString(36).slice(2);}
export function upload(path:string,sid:string):Promise<any>{return new Promise((resolve,reject)=>wx.uploadFile({url:config.apiBase+'/v1/files',filePath:path,name:'file',formData:{student_id:sid},header:{Authorization:'Bearer '+token()},timeout:60000,success:r=>{try{const d=JSON.parse(r.data);if(r.statusCode===200)resolve(d);else reject(new ApiError(r.statusCode,d.detail||'上传失败'));}catch{reject(new ApiError(502,'上传响应无效'));}},fail:()=>reject(new ApiError(0,'图片上传失败，请重试'))}));}
export async function ticket(fid:string,purpose='preview',sid=activeStudent()){return request('/v1/files/'+fid+'/tickets','POST',{purpose,student_id:sid||null});}
export function message(e:any){return e?.message||'操作未完成，请重试';}
// API instants are UTC; teaching schedules are displayed in China standard time.
export function date(value:string){if(!value)return '';if(value.length===10)return value;const utc=new Date(value.endsWith('Z')||/[+-]\d\d:\d\d$/.test(value)?value:value+'Z');if(isNaN(utc.getTime()))return '';const china=new Date(utc.getTime()+8*3600000);return china.toISOString().replace('T',' ').slice(0,16);}
export function downloadFile(url:string):Promise<WechatMiniprogram.DownloadFileSuccessCallbackResult>{return new Promise((resolve,reject)=>wx.downloadFile({url,success:resolve,fail:reject}));}
