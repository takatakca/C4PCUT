import {test} from "node:test";
import assert from "node:assert/strict";
import {createV1BillingLookup,grantFromSubscription} from "./v1-billing-adapter.mjs";
import {createIssuer,AccessDenied} from "./studio-issuer.mjs";
const client="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",other="bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb";
const row={clientId:client,planKey:"c4pcut_standard",status:"active",stripeSubscriptionId:"sub_example123",currentPeriodEnd:new Date(200000)};
test("active verified period maps to a dedicated bounded grant",()=>{
  assert.deepEqual(grantFromSubscription(row,client,100),{clientId:client,product:"c4pcut",plan:"standard",active:true,status:"active",validFrom:100,validUntil:200});
  for(const patch of [{status:"trialing"},{status:"past_due"},{status:"canceled"},{planKey:"ai_file_organizer"},{stripeSubscriptionId:null},{currentPeriodEnd:null},{currentPeriodEnd:new Date(100000)},{clientId:other}])assert.equal(grantFromSubscription({...row,...patch},client,100),null);
});
test("database lookup stays client-scoped and fails closed",async()=>{
  let rows=[row],calls=0;
  const env={TAKATAK_C4PCUT_BILLING_READ_ENABLED:"true"};
  const getPrisma=()=>({growthSubscription:{findMany:async query=>{
    calls++;assert.deepEqual(query.where,{clientId:client,planKey:{in:["c4pcut_standard","c4pcut_pro"]}});assert.equal(query.take,3);return rows;
  }}});
  const lookup=createV1BillingLookup({getPrisma,env,clock:()=>100000});
  assert.equal((await lookup(client)).plan,"standard");
  rows=[row,{...row,planKey:"c4pcut_pro"}];assert.equal(await lookup(client),null);
  rows=[row,{...row,planKey:"c4pcut_pro",status:"canceled"}];assert.equal((await lookup(client)).plan,"standard");
  rows=[{...row,clientId:other}];assert.equal(await lookup(client),null);
  rows=[row,row];assert.equal(await lookup(client),null);
  rows=[];assert.equal(await lookup(client),null);
  const count=calls;env.TAKATAK_C4PCUT_BILLING_READ_ENABLED="false";assert.equal(await lookup(client),null);assert.equal(calls,count);
});
test("reference issuer uses billing lookup and stops signing on cancellation",async()=>{
  let rows=[row];
  const env={TAKATAK_C4PCUT_BILLING_READ_ENABLED:"true",TAKATAK_C4PCUT_GATEWAY_ENABLED:"true"};
  const lookup=createV1BillingLookup({env,getPrisma:()=>({growthSubscription:{findMany:async()=>rows}}),clock:()=>100000});
  const issue=createIssuer({env,studioEnabled:()=>true,requireWorkspaceApiPermission:async()=>({ok:true,access:{mode:"client_scoped",activeClientId:client,profileId:other}}),lookupEntitlement:lookup,readKey:async()=>"ab".repeat(32),clock:()=>100000,nonce:()=>"c".repeat(32)});
  const request={method:"GET",target:"/api/session",body:Buffer.alloc(0)};
  assert.ok((await issue(request)).header);
  rows=[{...row,status:"canceled"}];await assert.rejects(issue(request),AccessDenied);
});
