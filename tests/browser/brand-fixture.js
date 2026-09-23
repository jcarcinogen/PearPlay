// Deterministic display/test data ONLY. Installed popup source is never modified.
// Injected through CDP into an isolated Chrome extension document before popup.js.
// No native helper, LAN receiver, credentials, real media or personal browser profile.
(() => {
  const f = window.__fixture = {
    calls: [], allowed: true, fail: false, hold: null,
    view: { enabled: true, selected: 'example-video', receiver: 'example-receiver', localAvailable: false,
      candidates: [{id:'example-video', label:'A film from this page', videoId:'example-element'}],
      native: { state:'idle', evidence:'none', error:null,
        receivers:[{identifier:'example-receiver',address:'192.0.2.10',label:'Living Room'}],
        capabilities:['hello','discover','start','status','stop'] } }
  };
  chrome.tabs.query = async () => [{id:1,url:'https://example.test/watch'}];
  chrome.tabs.reload = async () => { f.calls.push({op:'reload'}); };
  chrome.permissions.getAll = async () => ({origins:f.allowed?['http://*/*','https://*/*']:[]});
  chrome.permissions.request = async args => {f.calls.push({op:'grant',...args});if(args.origins.length===2)f.allowed=true;return true;};
  chrome.storage.session.get = async () => ({});
  chrome.storage.session.set = async () => {};
  chrome.runtime.sendMessage = async message => {
    const {op}=message;
    // PIN values are deliberately never retained, even in fixtures.
    f.calls.push(op==='pair'?{op}:structuredClone(message));
    if(op==='view') return structuredClone(f.view);
    if(f.fail) throw Error('NATIVE_DISCONNECTED');
    if(f.hold) await new Promise(resolve => {f.release=resolve;});
    if(op==='enable') f.view.enabled=true;
    if(op==='disable') f.view.enabled=false;
    if(op==='select') f.view.selected=message.id;
    if(op==='receiver') f.view.receiver=message.id;
    if(op==='start') {f.view.native.state='playing';f.view.native.evidence='protocol';}
    if(op==='stop') {f.view.native.state='stopped';f.view.native.evidence='unverified';}
    if(op==='localPause') {if(message.confirmed!==true)throw Error('CONFIRM_TV_FIRST');f.view.localAvailable=true;}
    if(op==='pairBegin') return {ok:true};
    if(op==='pair') f.view.native.error=null;
    if(op==='discover') return {receivers:structuredClone(f.view.native.receivers)};
    return ['enable','rescan'].includes(op)?{scanned:1,total:1}:{ok:true};
  };
})();
