import {spawn} from 'node:child_process';
import {existsSync, mkdtempSync, readFileSync, realpathSync, rmSync} from 'node:fs';
import {join} from 'node:path';
import {tmpdir} from 'node:os';
import {setTimeout as delay} from 'node:timers/promises';

// Dedicated disposable profile; never attach to an existing browser or native host.
export async function chromeSession({profileDirectory='',prepare=()=>{},isolateHome=false}={}) {
  const binary = process.env.CHROME || ['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome','/opt/google/chrome/chrome','/usr/bin/google-chrome'].find(existsSync);
  if (!binary) throw Error('Installed Google Chrome required; set CHROME. No download is performed.');
  const root=realpathSync(mkdtempSync(join(tmpdir(),'pearplay-brand-')));
  if(profileDirectory.split('/').includes('..')||profileDirectory.startsWith('/'))throw Error('Profile must remain inside owned root');
  const profile=join(root,profileDirectory);
  try {await prepare(root);}catch(error){rmSync(root,{recursive:true,force:true});throw error;}
  const child=spawn(binary,['--headless=new','--disable-gpu',`--user-data-dir=${profile}`,'--remote-debugging-address=127.0.0.1','--remote-debugging-port=0','--enable-unsafe-extension-debugging','--no-first-run','--no-default-browser-check','--disable-background-networking','--disable-component-update','--disable-sync','--hide-scrollbars','about:blank'],{stdio:['ignore','ignore','pipe'],env:isolateHome?{...process.env,HOME:join(root,'home'),XDG_CONFIG_HOME:join(root,'home/.config')}:process.env});
  let startupLog='';child.stderr.on('data',chunk=>{startupLog=(startupLog+chunk.toString()).slice(-2000);});
  let ws; let exited=false; child.on('exit',()=>{exited=true;});
  const pending=new Map(); let serial=0;
  const events=[];
  async function close() {
    ws?.close();
    if(!exited) child.kill('SIGTERM');
    for(let i=0;i<100&&!exited;i++) await delay(50);
    if(!exited) {child.kill('SIGKILL'); await new Promise(r=>child.once('exit',r));}
    for(const p of pending.values()){clearTimeout(p.timer);p.reject(Error('Chrome closed'));}
    pending.clear();
    rmSync(root,{recursive:true,force:true}); // Only this invocation's mkdtemp directory.
  }
  try {
    child.on('error',()=>{exited=true;});
    for(let i=0;i<200&&!existsSync(join(profile,'DevToolsActivePort'))&&!exited;i++) await delay(50);
    if(!existsSync(join(profile,'DevToolsActivePort'))) throw Error('Owned Chrome did not become ready: '+startupLog);
    const [port,path]=readFileSync(join(profile,'DevToolsActivePort'),'utf8').trim().split('\n');
    ws=new WebSocket(`ws://127.0.0.1:${port}${path}`);
    await new Promise((resolve,reject)=>{ws.onopen=resolve;ws.onerror=reject;});
    ws.onmessage=e=>{
      const m=JSON.parse(e.data);
      if(m.id){const p=pending.get(m.id);if(!p)return;pending.delete(m.id);clearTimeout(p.timer);m.error?p.reject(Error(`${p.method}: ${m.error.message}`)):p.resolve(m.result);}
      else events.push(m);
    };
    const send=(method,params={},sessionId)=>new Promise((resolve,reject)=>{
      const id=++serial;
      const timer=setTimeout(()=>{pending.delete(id);reject(Error(`CDP timeout: ${method}`));},20000);
      pending.set(id,{resolve,reject,timer,method});ws.send(JSON.stringify({id,method,params,...(sessionId?{sessionId}:{})}));
    });
    const evaluate=async(sessionId,expression)=>{
      const result=await send('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true,userGesture:true},sessionId);
      if(result.exceptionDetails)throw Error('Page evaluation failed (raw page data omitted)');
      return result.result.value;
    };
    return {send,evaluate,events,close,version:(await send('Browser.getVersion')).product};
  } catch(error) {await close();throw error;}
}
