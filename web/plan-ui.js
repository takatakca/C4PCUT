/* Presentation only: server remains the authorization boundary. */
"use strict";
const PlanUI = (() => {
  const edges={vertical:1280,square:720,landscape:1280,vertical_hd:1920,square_hd:1080,landscape_hd:1920,landscape_qhd:2560,vertical_qhd:2560,landscape_4k:3840,vertical_4k:3840};
  function feature(policy,name){return !policy||policy.features.includes(name);}
  function preset(policy,name,source){
    if(!policy)return true;
    const edge=name==="original"?(source?Math.max(source.width,source.height):0):edges[name];
    return Number.isFinite(edge)&&edge<=policy.max_output_edge;
  }
  function quality(policy,name){return !policy||policy.qualities.includes(name);}
  function render(policy,settings,source,seconds){
    if(!policy)return true;
    return preset(policy,settings.preset,source)&&quality(policy,settings.quality)&&seconds<=policy.max_render_seconds&&
      (settings.caption_mode==="soft"||feature(policy,"animated_captions"))&&(!settings.use_music||feature(policy,"music"));
  }
  function usage(data){
    if(!data||data.enabled===false||!Number.isFinite(data.attempted_seconds)||data.attempted_seconds<0)return null;
    const used=data.attempted_seconds,cap=data.limit_seconds;
    if(cap===null)return {label:used+" s attempted · no cap",ratio:null};
    if(!Number.isFinite(cap)||cap<0)return null;
    return {label:used+" / "+cap+" s attempted · "+Math.max(0,cap-used)+" s remaining",ratio:cap===0?1:Math.min(1,used/cap)};
  }
  return Object.freeze({feature,preset,quality,render,usage});
})();
