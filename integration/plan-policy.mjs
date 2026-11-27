// Server-only product grant policy. Catalog prices are NOT access grants.
import {readFileSync} from "node:fs";
const UUID=/^[a-f0-9]{8}-(?:[a-f0-9]{4}-){3}[a-f0-9]{12}$/;
const CODES=["free","standard","pro"];
export function validateCatalog(value){
  if(!value||value.version!==1||value.currency!=="CAD"||value.billing_enabled!==false||!Array.isArray(value.plans)||value.plans.length!==3)throw new Error("Invalid disabled pricing catalog");
  const seen=new Set();
  for(const plan of value.plans){
    if(!plan||!CODES.includes(plan.code)||seen.has(plan.code)||!Number.isSafeInteger(plan.monthly_minor_units)||plan.monthly_minor_units<0||(plan.code==="free"?plan.monthly_minor_units!==0:plan.monthly_minor_units===0))throw new Error("Invalid plan price");
    seen.add(plan.code);
  }
  if(value.plans.find(p=>p.code==="standard").monthly_minor_units>=value.plans.find(p=>p.code==="pro").monthly_minor_units)throw new Error("Invalid plan ordering");
  if(value.annual_prices!==null||value.entitlements!==null)throw new Error("Unapproved annual pricing or feature allowances");
  return Object.freeze({currency:"CAD",billing_enabled:false,plans:Object.freeze(value.plans.map(p=>Object.freeze({code:p.code,monthly_minor_units:p.monthly_minor_units}))),annual_prices:null,entitlements:null});
}
export function loadCatalog(){return validateCatalog(JSON.parse(readFileSync(new URL("../config/pricing.ca.json",import.meta.url),"utf8")));}
export function activeGrant(grant,clientId,now){
  if(typeof clientId!=="string"||!UUID.test(clientId)||!Number.isSafeInteger(now)||now<0||!grant||grant.clientId!==clientId||grant.product!=="c4pcut"||grant.active!==true||!CODES.includes(grant.plan)||grant.status!=="active")return false;
  // Explicit bounded grant, including free access. No infinite implicit grants.
  return Number.isSafeInteger(grant.validFrom)&&Number.isSafeInteger(grant.validUntil)&&grant.validFrom>=0&&grant.validFrom<=now&&now<grant.validUntil;
}
