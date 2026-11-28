// Server-only reference adapter for the private C4PCUT gateway v3.
// Never bundle into a browser; do not expose an endpoint that returns assertions.
import { createHash, createHmac, randomBytes } from "node:crypto";
import {activeGrant} from "./plan-policy.mjs";
const UUID=/^[a-f0-9]{8}-(?:[a-f0-9]{4}-){3}[a-f0-9]{12}$/;
const KEY=/^[a-f0-9]{64}$/;
const ID="[a-f0-9]{32}";
const GET=new RegExp("^(?:/api/(?:session|usage)|/api/(?:source|export|captions|soundtrack|logo|pip)/"+ID+"|/api/thumbnail/"+ID+"/[0-9]{1,2}\\.jpg|/api/clipper/"+ID+"/[a-f0-9]{24}/[0-9]\\.mp4)$");
const POST=new Set(["/api/projects/list","/api/projects/open","/api/projects/save","/api/projects/delete","/api/analyze","/api/scenes/split","/api/visuals","/api/captions/import","/api/transcribe","/api/music/analyze","/api/music/cuts","/api/director","/api/clipper/suggest","/api/clipper/render","/api/render","/api/render/status","/api/render/cancel","/api/studio/import-pack","/api/import"]);
const PIP=new RegExp("^/api/pip/import/"+ID+"$");
const LOGO=new RegExp("^/api/logo/import/"+ID+"$");
const MUSIC=new RegExp("^/api/music/import/"+ID+"$");
export class AccessDenied extends Error {}
function deny(){throw new AccessDenied("C4PCUT access denied");}
function routeLimit(method,target){
  if(typeof target!=="string")deny();
  if(method==="GET"&&GET.test(target))return 0;
  if(method==="POST"&&(POST.has(target)||MUSIC.test(target)||LOGO.test(target)||PIP.test(target))){
    if(target==="/api/import")return 250*1024*1024;
    if(MUSIC.test(target))return 64*1024*1024;
    if(LOGO.test(target))return 2*1024*1024;
    if(PIP.test(target))return 24*1024*1024;
    if(target==="/api/render/status"||target==="/api/render/cancel")return 1024;
    if(target==="/api/studio/import-pack")return 16384;
    return 262144;
  }
  deny();
}
export function createIssuer({env,requireWorkspaceApiPermission,studioEnabled,lookupEntitlement,readKey,clock=()=>Date.now(),nonce=()=>randomBytes(16).toString("hex")}){
  if(typeof requireWorkspaceApiPermission!=="function"||typeof studioEnabled!=="function"||typeof lookupEntitlement!=="function"||typeof readKey!=="function")throw new TypeError("Trusted server dependencies required");
  return async function issue({method,target,body}){
    if(env.TAKATAK_C4PCUT_GATEWAY_ENABLED!=="true"||!studioEnabled(env))deny();
    const limit=routeLimit(method,target);
    if(!Buffer.isBuffer(body)||body.length>limit||(method==="POST"&&body.length===0))deny();
    // Snapshot the exact forwarded bytes before asynchronous checks.
    const bytes=Buffer.from(body);
    const gate=await requireWorkspaceApiPermission("create_content");
    if(gate?.ok!==true||gate.access?.mode!=="client_scoped")deny();
    const {activeClientId,profileId}=gate.access;
    if(typeof activeClientId!=="string"||typeof profileId!=="string"||!UUID.test(activeClientId)||!UUID.test(profileId))deny();
    // Must use dedicated, authoritative product state; never Social bypass or browser input.
    const grant=await lookupEntitlement(activeClientId,profileId);
    if(!activeGrant(grant,activeClientId,Math.floor(clock()/1000)))deny();
    const key=await readKey();
    if(typeof key!=="string"||!KEY.test(key))deny();
    const iat=Math.floor(clock()/1000), n=nonce();
    if(!Number.isSafeInteger(iat)||iat<0||typeof n!=="string"||!/^[a-f0-9]{32}$/.test(n))deny();
    if(!activeGrant(grant,activeClientId,iat))deny();
    const claims={iss:"takatak-studio-gateway",aud:"c4pcut-private-v3",sub:profileId,
      client_id:activeClientId,permission:"create_content",entitlement:"c4pcut_active",plan:grant.plan,
      iat,exp:Math.min(iat+30,grant.validUntil),nonce:n,method,target,body_sha256:createHash("sha256").update(bytes).digest("hex")};
    const encoded=Buffer.from(JSON.stringify(claims),"utf8").toString("base64url");
    const signature=createHmac("sha256",Buffer.from(key,"hex")).update(encoded,"ascii").digest("base64url");
    return {header:encoded+"."+signature,body:bytes};
  };
}
