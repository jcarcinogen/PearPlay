// Guest-only real Chrome sandbox evidence; canonical session launcher, no security overrides.
import assert from 'node:assert/strict';
import {writeFileSync,readFileSync} from 'node:fs';
import {execFileSync} from 'node:child_process';
import {chromeSession} from './chrome-session.mjs';
import {setTimeout as delay} from 'node:timers/promises';
assert.equal(process.platform,'linux');
const c=await chromeSession({isolateHome:true,profileDirectory:'google-chrome'});
try {
  const {targetId}=await c.send('Target.createTarget',{url:'chrome://sandbox'});
  const {sessionId}=await c.send('Target.attachToTarget',{targetId,flatten:true});
  await c.send('Runtime.enable',{},sessionId);
  let text='';
  for(let i=0;i<100;i++){
    text=await c.evaluate(sessionId,'document.body.innerText');
    if(text.includes('Seccomp'))break;
    await delay(100);
  }
  assert.match(text,/Layer 1 Sandbox\s+Namespace/i);
  assert.match(text,/PID namespaces\s+Yes/i);
  assert.match(text,/Network namespaces\s+Yes/i);
  assert.match(text,/Seccomp-BPF sandbox\s+Yes/i);
  const data={browser:c.version,executable:'/opt/google/chrome/chrome',sandboxPage:text,
    executableSha256:execFileSync('sha256sum',['/opt/google/chrome/chrome'],{encoding:'utf8'}).split(' ')[0],
    package:execFileSync('dpkg-query',['-W','google-chrome-stable'],{encoding:'utf8'}).trim(),
    apparmorPolicy:execFileSync('sysctl',['kernel.apparmor_restrict_unprivileged_userns'],{encoding:'utf8'}).trim(),
    launchSource:'/src/scripts/chrome-session.mjs',sandboxOverrides:false};
  writeFileSync('/work/evidence/chrome-sandbox.json',JSON.stringify(data,null,2)+'\n');
  console.log(JSON.stringify(data,null,2));
} finally {await c.close();}
