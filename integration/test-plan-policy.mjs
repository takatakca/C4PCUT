import {test} from "node:test";
import assert from "node:assert/strict";
import {activeGrant,loadCatalog,validateCatalog} from "./plan-policy.mjs";
import {createIssuer,AccessDenied} from "./studio-issuer.mjs";
const client="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",profile="bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb";
const grant={clientId:client,product:"c4pcut",plan:"free",status:"active",active:true,validFrom:100,validUntil:200};
test("catalog reflects approved monthly CAD reference, not access or payments",()=>{
  const catalog=loadCatalog();
  assert.deepEqual(catalog.plans,[{code:"free",monthly_minor_units:0},{code:"standard",monthly_minor_units:1349},{code:"pro",monthly_minor_units:2799}]);
  assert.equal(catalog.billing_enabled,false);
  assert.equal(catalog.entitlements,null);
  for(const patch of [{billing_enabled:true},{currency:"USD"},{annual_prices:{}},{entitlements:{}},{plans:[catalog.plans[0],catalog.plans[0],catalog.plans[2]]}])assert.throws(()=>validateCatalog({version:1,...catalog,...patch}));
});
test("only explicit, current, dedicated grants qualify, including free",()=>{
  assert.equal(activeGrant(grant,client,100),true);
  assert.equal(activeGrant(grant,client,199),true);
  assert.equal(activeGrant(grant,client,200),false);
  assert.equal(activeGrant(grant,client,99),false);
  for(const patch of [{active:false},{status:"cancelled"},{status:"past_due"},{product:"social"},{plan:"unknown"},{validUntil:null},{clientId:profile}])assert.equal(activeGrant({...grant,...patch},client,150),false);
  assert.equal(activeGrant({clientId:client,product:"c4pcut",active:true},client,150),false);
});
test("signature expires with grant and rejects grants expired while reading key",async()=>{
  const config={env:{TAKATAK_C4PCUT_GATEWAY_ENABLED:"true"},studioEnabled:()=>true,requireWorkspaceApiPermission:async()=>({ok:true,access:{mode:"client_scoped",activeClientId:client,profileId:profile}}),lookupEntitlement:async()=>grant,readKey:async()=>"ab".repeat(32),clock:()=>195000,nonce:()=>"c".repeat(32)};
  const request={method:"GET",target:"/api/session",body:Buffer.alloc(0)};
  const result=await createIssuer(config)(request);
  const claims=JSON.parse(Buffer.from(result.header.split(".")[0],"base64url"));
  assert.equal(claims.exp,200);
  let calls=0;
  await assert.rejects(createIssuer({...config,clock:()=>++calls===1?195000:200000})(request),AccessDenied);
});
