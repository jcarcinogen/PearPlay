export const minimumHelperVersion='0.2.0';
export function connectionState(helper,error=null) {
  if(error==='NATIVE_DISCONNECTED')return {kind:'missing',text:'This browser cannot find or start PearPlay Helper. Install it, or open PearPlay Setup and connect this browser. Then fully quit and reopen the browser.'};
  if(error||!helper)return {kind:'broken',text:'PearPlay Helper did not answer correctly. End any casting session, reopen your browser and check again. If needed, reinstall the helper.'};
  const v=helper.helperVersion;
  const parts=typeof v==='string'&&/^\d{1,4}\.\d{1,4}\.\d{1,4}$/.test(v)?v.split('.').map(Number):[];
  const minimum=minimumHelperVersion.split('.').map(Number);
  const older=!parts.length||parts.some((n,i)=>n<minimum[i]&&parts.slice(0,i).every((p,j)=>p===minimum[j]));
  if(older||!['hello','discover','start'].every(op=>helper.capabilities?.includes(op)))return {kind:'update',text:'Your helper needs an update. End any casting session, install the latest helper, then fully quit and reopen this browser.'};
  return {kind:'ready',text:'PearPlay Helper connected. You’re ready to find your Apple TV.'};
}
export function downloadsFor(catalog,platform,extensionId) {
  if(!catalog||catalog.extensionId!==extensionId||!Array.isArray(catalog.downloads))return [];
  return catalog.downloads.filter(item=>{
    if(item?.os!==platform.os||item?.arch!==platform.arch||!['pkg','deb','rpm','pkg.tar.zst'].includes(item.format))return false;
    try { const url=new URL(item.url);return url.protocol==='https:'&&url.host==='github.com'&&!url.username&&!url.password&&!url.search&&!url.hash&&url.pathname.startsWith('/jcarcinogen/PearPlay/releases/download/'); } catch { return false; }
  });
}
