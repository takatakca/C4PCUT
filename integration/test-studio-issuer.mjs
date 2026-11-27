import {test} from "node:test";
import assert from "node:assert/strict";
import {createHash,createHmac} from "node:crypto";
import {createIssuer,AccessDenied} from "./studio-issuer.mjs";
const client="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",profile="bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",key="ab".repeat(32);
const defaults={env:{TAKATAK_C4PCUT_GATEWAY_ENABLED:"true",TAKATAK_STUDIO_ENABLED:"true"},studioEnabled:e=>e.TAKATAK_STUDIO_ENABLED==="true",requireWorkspaceApiPermission:async p=>{assert.equal(p,"create_content");return {ok:true,access:{mode:"client_scoped",activeClientId:client,profileId:profile}}},lookupEntitlement:async (c,p)=>{assert.equal(c,client);assert.equal(p,profile);return {clientId:client,product:"c4pcut",active:true,plan:"pro",status:"active",validFrom:900,validUntil:1100}},readKey:async()=>key,clock:()=>1000000,nonce:()=>"c".repeat(32)};
test("verified access produces receiver-compatible signature and exact bytes",async()=>{
  const body=Buffer.from('{"id":"example"}');
  const result=await createIssuer(defaults)({method:"POST",target:"/api/projects/save",body,clientId:"untrusted"});
  const [encoded,signature]=result.header.split(".");
  assert.equal(createHmac("sha256",Buffer.from(key,"hex")).update(encoded).digest("base64url"),signature);
  const claims=JSON.parse(Buffer.from(encoded,"base64url"));
  assert.equal(claims.client_id,client);assert.equal(claims.sub,profile);
  assert.equal(claims.exp-claims.iat,30);
  assert.equal(claims.body_sha256,createHash("sha256").update(body).digest("hex"));
  assert.deepEqual(result.body,body);
});
test("fail closed on disabled flags, access, entitlement and missing key",async()=>{
  const cases=[{env:{}},{studioEnabled:()=>false},{requireWorkspaceApiPermission:async()=>({ok:false})},{requireWorkspaceApiPermission:async()=>({ok:true,access:{mode:"platform_admin"}})},{lookupEntitlement:async()=>null},{lookupEntitlement:async()=>({clientId:client,product:"social",active:true})},{lookupEntitlement:async()=>({clientId:profile,product:"c4pcut",active:true})},{lookupEntitlement:async()=>({clientId:client,product:"c4pcut",active:false})},{readKey:async()=>""}];
  for(const overrides of cases)await assert.rejects(createIssuer({...defaults,...overrides})({method:"GET",target:"/api/session",body:Buffer.alloc(0)}),AccessDenied);
});
test("reject arbitrary URLs, query strings, unauthorized methods and oversized bodies",async()=>{
  const issue=createIssuer(defaults);
  for(const target of ["https://evil.example/","//evil.example","/api/session?x=1","/api/source/../x","/healthz","/api/unknown"])await assert.rejects(issue({method:"GET",target,body:Buffer.alloc(0)}),AccessDenied);
  await assert.rejects(issue({method:"DELETE",target:"/api/session",body:Buffer.alloc(0)}),AccessDenied);
  await assert.rejects(issue({method:"POST",target:"/api/render/cancel",body:Buffer.alloc(1025)}),AccessDenied);
});
