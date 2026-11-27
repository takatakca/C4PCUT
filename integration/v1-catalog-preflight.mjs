// Read-only catalog reconciliation against the observed TAKATAK Prisma shape.
// Never call a write method, generate Stripe IDs, or activate a price.
import {loadCatalog} from "./plan-policy.mjs";
const names=Object.freeze({free:"C4PCUT Free",standard:"C4PCUT Standard",pro:"C4PCUT Pro"});
export function desiredCatalog(){
  const catalog=loadCatalog();
  return {code:"c4pcut",name:"C4PCUT",status:"draft",
    plans:catalog.plans.map(p=>({code:p.code,legacyCode:p.code==="free"?null:"c4pcut_"+p.code,name:names[p.code],status:"draft",selfServeEligible:false,
      prices:p.code==="free"?[]:[{currency:"CAD",unitAmountMinor:p.monthly_minor_units,billingInterval:"month",intervalCount:1,provider:"stripe",providerPriceId:null,active:false}]})),entitlements:[]};
}
const planFields=["code","legacyCode","name","status","selfServeEligible"];
const priceFields=["currency","unitAmountMinor","billingInterval","intervalCount","provider","providerPriceId","active"];
function equalFields(a,b,fields){return fields.every(key=>a?.[key]===b?.[key]);}
export function compareCatalog(actual,desired=desiredCatalog()){
  if(actual===null)return {status:"missing",changes:["product","plans","inactive_monthly_prices"],writes:0};
  if(!actual||typeof actual!=="object"||!Array.isArray(actual.plans)||!Array.isArray(actual.entitlements))return {status:"blocked",conflicts:["invalid_catalog_response"],writes:0};
  const conflicts=[],missing=[];
  if(!equalFields(actual,desired,["code","name","status"]))conflicts.push("product_metadata_or_status");
  if(actual.entitlements.length)conflicts.push("existing_entitlements");
  const seen=new Set();
  for(const plan of actual.plans){
    const want=desired.plans.find(p=>p.code===plan?.code);
    if(!want||seen.has(plan.code)){conflicts.push("unknown_or_duplicate_plan");continue;}
    seen.add(plan.code);
    if(!equalFields(plan,want,planFields))conflicts.push(plan.code+":metadata_or_status");
    if(!Array.isArray(plan.prices)||!Array.isArray(plan.entitlements)){conflicts.push(plan.code+":invalid_relations");continue;}
    if(plan.entitlements.length)conflicts.push(plan.code+":existing_entitlements");
    if(plan.prices.length===0&&want.prices.length===1)missing.push(plan.code+":monthly_price");
    else if(plan.prices.length!==want.prices.length||plan.prices.some((p,i)=>!equalFields(p,want.prices[i],priceFields)))conflicts.push(plan.code+":price_conflict");
  }
  for(const plan of desired.plans)if(!seen.has(plan.code))missing.push(plan.code+":plan");
  return {status:conflicts.length?"blocked":missing.length?"missing":"matches_disabled_catalog",conflicts,changes:missing,writes:0};
}
export async function preflightCatalog({getPrisma,env}){
  if(env?.TAKATAK_C4PCUT_CATALOG_READ_ENABLED!=="true")return {status:"disabled",writes:0};
  try{
    const db=await getPrisma();
    if(!db)return {status:"unavailable",writes:0};
    const actual=await db.productCatalog.findUnique({where:{code:"c4pcut"},select:{code:true,name:true,status:true,entitlements:{select:{code:true},take:1},plans:{take:4,select:{code:true,legacyCode:true,name:true,status:true,selfServeEligible:true,entitlements:{select:{entitlementId:true},take:1},prices:{take:2,select:{currency:true,unitAmountMinor:true,billingInterval:true,intervalCount:true,provider:true,providerPriceId:true,active:true}}}}}});
    return compareCatalog(actual);
  }catch{return {status:"unavailable",writes:0};}
}
