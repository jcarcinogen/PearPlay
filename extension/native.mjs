import {httpURL} from './core.mjs';
const ops=['hello','discover','start','status','stop','pause','resume'];
export function literalIP(s) {
 if(typeof s!=='string') return false;
 if(/^\d+\.\d+\.\d+\.\d+$/.test(s)) return s.split('.').every(x=>String(Number(x))===x&&Number(x)<=255);
 if(!/^[\da-f:]+$/i.test(s)||!s.includes(':')) return false;
 try { return new URL(`http://[${s}]/`).hostname.startsWith('['); }catch{return false;}
}
export class Native {
 constructor(connect,{timeout=15000}={}) {this.connect=connect;this.timeout=timeout;this.pending=new Map();this.serial=0;this.applied=0;this.port=null;this.state={state:'idle',evidence:'none',capabilities:[],receivers:[]};}
 view(){return structuredClone(this.state);}
 fail(code){this.state={state:'error',evidence:'none',capabilities:[],receivers:[],error:code};for(const p of this.pending.values()){clearTimeout(p.timer);p.reject(Error(code));}this.pending.clear();const old=this.port;this.port=null;old?.disconnect();}
 async request(op,args={}) {
 const keys=Object.keys(args);
 if(!ops.includes(op)|| (op==='start' ? !(keys.length===3&&typeof args.receiver==='string'&&args.receiver.length>0&&args.receiver.length<=1024&&literalIP(args.host)&&httpURL(args.url)) : op==='discover' ? !(keys.length===0 || keys.length===1&&literalIP(args.host)) : keys.length!==0)) throw Error('INVALID_REQUEST');
 if(this.pending.size>=16) throw Error('NATIVE_BUSY');
 if(!this.port){try{const port=this.connect();this.port=port;port.onDisconnect.addListener(()=>{if(this.port===port)this.fail('NATIVE_DISCONNECTED');});port.onMessage.addListener(m=>{if(this.port===port)this.receive(m);});}catch{this.fail('NATIVE_DISCONNECTED');throw Error('NATIVE_DISCONNECTED');}}
 const id=`p${++this.serial}`;const message={v:1,id,op,args};
 if(new TextEncoder().encode(JSON.stringify(message)).length>65536) throw Error('INVALID_REQUEST');
 return new Promise((resolve,reject)=>{const timer=setTimeout(()=>this.fail('NATIVE_TIMEOUT'),this.timeout);this.pending.set(id,{resolve,reject,timer,serial:this.serial});try{this.port.postMessage(message);}catch{this.fail('NATIVE_DISCONNECTED');}});
 }
 receive(m){
 if(!m||new TextEncoder().encode(JSON.stringify(m)).length>65536||m.v!==1||typeof m.ok!=='boolean'||!['idle','connecting','playing','paused','stopping','stopped','error'].includes(m.state)||!['none','protocol','unverified'].includes(m.evidence)||!Array.isArray(m.capabilities)||m.capabilities.some(x=>!ops.includes(x))) {this.fail('INVALID_RESPONSE');return;}
 if(m.receivers!==undefined&&(!Array.isArray(m.receivers)||m.receivers.some(r=>!r||typeof r.identifier!=='string'||!r.identifier.length||r.identifier.length>1024||!literalIP(r.address)))) {this.fail('INVALID_RESPONSE');return;}
 const pending=this.pending.get(m.id);if(!pending&&m.id!=='event')return;
 if(pending&&pending.serial<this.applied){clearTimeout(pending.timer);this.pending.delete(m.id);if(m.ok)pending.resolve(this.view());else pending.reject(Error('HELPER_ERROR'));return;}
 this.applied=pending?.serial??this.serial;
 const receivers=Array.isArray(m.receivers)?m.receivers.slice(0,64).map((r,i)=>({identifier:r.identifier,address:r.address,label:`Receiver ${i+1} (${r.address})` })):this.state.receivers;
 this.state={state:m.ok?m.state:'error',evidence:m.evidence,capabilities:[...m.capabilities],receivers,error:m.ok?null:'HELPER_ERROR'};
 if(pending){clearTimeout(pending.timer);this.pending.delete(m.id);if(m.ok)pending.resolve(this.view());else pending.reject(Error('HELPER_ERROR'));}
 }
}
