// Server-only read-only adapter candidate for TAKATAK V1 GrowthSubscription.
// Proposed SKU keys; no catalog registration, database migration, or checkout.
const UUID=/^[a-f0-9]{8}-(?:[a-f0-9]{4}-){3}[a-f0-9]{12}$/;
const KEYS=Object.freeze({c4pcut_standard:"standard",c4pcut_pro:"pro"});
export function grantFromSubscription(row,clientId,now){
  if(typeof clientId!=="string"||!UUID.test(clientId)||!Number.isSafeInteger(now)||now<0||!row||row.clientId!==clientId||!Object.hasOwn(KEYS,row.planKey)||row.status!=="active"||typeof row.stripeSubscriptionId!=="string"||!/^sub_[A-Za-z0-9]+$/.test(row.stripeSubscriptionId))return null;
  // V1 schema provides currentPeriodEnd, not a verified period start.
  // The resulting access grant starts at observation time, not an invented date.
  const end=row.currentPeriodEnd instanceof Date?row.currentPeriodEnd:typeof row.currentPeriodEnd==="string"?new Date(row.currentPeriodEnd):null;
  const until=end?Math.floor(end.getTime()/1000):NaN;
  if(!Number.isSafeInteger(until)||until<=now)return null;
  return {clientId,product:"c4pcut",plan:KEYS[row.planKey],active:true,status:"active",validFrom:now,validUntil:until};
}
export function createV1BillingLookup({getPrisma,env,clock=()=>Date.now()}){
  if(typeof getPrisma!=="function"||!env)throw new TypeError("Server dependencies required");
  return async function lookupEntitlement(clientId){
    if(env.TAKATAK_C4PCUT_BILLING_READ_ENABLED!=="true"||typeof clientId!=="string"||!UUID.test(clientId))return null;
    try{
      const db=await getPrisma();
      if(!db)return null;
      const rows=await db.growthSubscription.findMany({
        where:{clientId,planKey:{in:Object.keys(KEYS)}},
        select:{clientId:true,planKey:true,status:true,stripeSubscriptionId:true,currentPeriodEnd:true},
        take:3
      });
      if(!Array.isArray(rows)||rows.length===0||rows.length>2)return null;
      // A duplicate or foreign row signals an inconsistent authoritative result.
      const seen=new Set();
      for(const row of rows){
        if(!row||row.clientId!==clientId||!Object.hasOwn(KEYS,row.planKey)||seen.has(row.planKey))return null;
        seen.add(row.planKey);
      }
      const now=Math.floor(clock()/1000);
      const grants=rows.map(row=>grantFromSubscription(row,clientId,now)).filter(Boolean);
      // An overlapping paid plan is ambiguous; do not silently upgrade.
      return grants.length===1?grants[0]:null;
    }catch{return null;}
  };
}
