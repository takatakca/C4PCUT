/* Approximate source-time preview, never an exported render. */
"use strict";
const EffectPreview=(()=>{
  const neutral=()=>({effect:"none",filter:"none",scale:1});
  function at(clips,edits,selected,time,enabled){
    if(!enabled||!Number.isFinite(time))return neutral();
    const base=clips.find(c=>c.start<=time&&time<c.end);
    if(!base||!selected.has(base.id))return neutral();
    const edit=edits[base.id]||base;
    if(!Number.isFinite(edit.start)||!Number.isFinite(edit.end)||edit.end<=edit.start||time<edit.start||time>=edit.end)return neutral();
    const duration=edit.end-edit.start,elapsed=time-edit.start;
    switch(edit.effect){
      case "mono":return {effect:"mono",filter:"grayscale(1)",scale:1};
      case "warm":return {effect:"warm",filter:"sepia(0.13) saturate(1.06)",scale:1};
      case "contrast":return {effect:"contrast",filter:"contrast(1.15) saturate(1.10)",scale:1};
      case "fade":{
        const fade=Math.min(.35,duration/3);
        const brightness=Math.max(0,Math.min(1,elapsed/fade,(duration-elapsed)/fade));
        return {effect:"fade",filter:"brightness("+brightness.toFixed(4)+")",scale:1};
      }
      case "zoom":return {effect:"zoom",filter:"none",scale:1+.12*Math.max(0,Math.min(1,elapsed/duration))};
      default:return neutral();
    }
  }
  return Object.freeze({at});
})();
