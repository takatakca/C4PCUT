// Private operator-managed registry reference, never an automatic payment provider.
// The injected path must be provisioned by the server operator, never the browser.
import {readFile,stat} from "node:fs/promises";
import {activeGrant} from "./plan-policy.mjs";
const UUID=/^[a-f0-9]{8}-(?:[a-f0-9]{4}-){3}[a-f0-9]{12}$/;
export async function lookupPrivateGrant(path,clientId,now=Math.floor(Date.now()/1000)){
  if(typeof clientId!=="string"||!UUID.test(clientId))return null;
  try{
    const info=await stat(path);
    if(!info.isFile()||info.size>262144)return null;
    const raw=await readFile(path,"utf8");
    if(Buffer.byteLength(raw)>262144)return null;
    const data=JSON.parse(raw);
    if(data.version!==1||!data.grants||Array.isArray(data.grants)||typeof data.grants!=="object")return null;
    if(!Object.hasOwn(data.grants,clientId))return null;
    const row=data.grants[clientId];
    if(!activeGrant(row,clientId,now))return null;
    return {clientId,product:"c4pcut",active:true,plan:row.plan,status:"active",validFrom:row.validFrom,validUntil:row.validUntil};
  }catch{return null;}
}
