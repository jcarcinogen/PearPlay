import fs from 'node:fs';
export async function connect(root){
 const [port,path]=fs.readFileSync(`${root}/profile/DevToolsActivePort`,'utf8').trim().split('\n');
 const ws=new WebSocket(`ws://127.0.0.1:${port}${path}`);await new Promise((r,j)=>{ws.onopen=r;ws.onerror=j;});
 let serial=0;const pending=new Map();ws.onmessage=e=>{const m=JSON.parse(e.data);if(m.id){const p=pending.get(m.id);if(p){pending.delete(m.id);clearTimeout(p.timer);m.error?p.reject(Error(JSON.stringify(m.error))):p.resolve(m.result);}}};
 const send=(method,params={},sessionId)=>new Promise((resolve,reject)=>{const id=++serial;const timer=setTimeout(()=>{pending.delete(id);reject(Error(`timeout ${method}`));},20000);pending.set(id,{resolve,reject,timer});ws.send(JSON.stringify({id,method,params,...(sessionId?{sessionId}:{})}));});
 return {send,close:()=>ws.close(),eval:async(session,expression)=>{const r=await send('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true,userGesture:true},session);if(r.exceptionDetails)throw Error(JSON.stringify(r.exceptionDetails));return r.result.value;}};
}
if(process.argv[1]===new URL(import.meta.url).pathname){const c=await connect(process.argv[2]);try{console.log(JSON.stringify(await c.send(process.argv[3],JSON.parse(process.argv[4]||'{}')),null,2));}finally{c.close();}}
