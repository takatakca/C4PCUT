import {test} from "node:test";
import assert from "node:assert/strict";
import {desiredCatalog,compareCatalog,preflightCatalog} from "./v1-catalog-preflight.mjs";
function existing(){
  const desired=desiredCatalog();
  return {...desired,plans:desired.plans.map(p=>({...p,entitlements:[]}))};
}
test("catalog uses exact approved CAD minor units and cannot be purchased",()=>{
  const c=desiredCatalog();
  assert.equal(c.status,"draft");
  assert.equal(c.entitlements.length,0);
  assert.equal(c.plans[0].prices.length,0);
  assert.deepEqual(c.plans.slice(1).map(p=>p.prices[0].unitAmountMinor),[1349,2799]);
  for(const p of c.plans){assert.equal(p.selfServeEligible,false);assert.equal(p.status,"draft");for(const price of p.prices){assert.equal(price.active,false);assert.equal(price.providerPriceId,null);}}
});
test("reconcile without writing; active plans and existing price IDs are conflicts",()=>{
  assert.equal(compareCatalog(null).status,"missing");
  assert.equal(compareCatalog(existing()).status,"matches_disabled_catalog");
  let c=existing();c.plans.pop();assert.equal(compareCatalog(c).status,"missing");
  c=existing();c.plans[2].prices=[];assert.equal(compareCatalog(c).status,"missing");
  for(const mutate of [c=>c.status="active",c=>c.plans[1].selfServeEligible=true,c=>c.plans[1].prices[0].providerPriceId="price_existing",c=>c.plans[1].prices[0].unitAmountMinor=1,c=>c.plans[1].prices[0].active=true,c=>c.entitlements.push({code:"existing"}),c=>c.plans.push(c.plans[0])]){
    c=existing();mutate(c);assert.equal(compareCatalog(c).status,"blocked");
  }
});
test("read-only preflight is disabled by default and uses scoped exact query",async()=>{
  let reads=0;
  const db={productCatalog:{findUnique:async query=>{reads++;assert.deepEqual(query.where,{code:"c4pcut"});assert.equal(query.select.plans.take,4);return existing();}}};
  const getPrisma=()=>db;
  assert.deepEqual(await preflightCatalog({getPrisma,env:{}}),{status:"disabled",writes:0});
  assert.equal(reads,0);
  assert.equal((await preflightCatalog({getPrisma,env:{TAKATAK_C4PCUT_CATALOG_READ_ENABLED:"true"}})).status,"matches_disabled_catalog");
  assert.equal(reads,1);
  assert.equal((await preflightCatalog({getPrisma:()=>{throw Error("private error")},env:{TAKATAK_C4PCUT_CATALOG_READ_ENABLED:"true"}})).status,"unavailable");
});
