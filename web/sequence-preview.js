/* Source-time playback plan; does not render or change exported media. */
"use strict";
const SequencePreview=(()=>{
  function ordered(clips,selected,prior=[]){
    const valid=new Set(clips.filter(c=>selected.has(c.id)).map(c=>c.id));
    const order=[];
    for(const id of [...prior,...[...valid].sort((a,b)=>a-b)])if(valid.delete(id))order.push(id);
    return order;
  }
  function build(clips,edits,selected,order=[]){
    let total=0;
    const ranges=[];
    const byId=new Map(clips.map(c=>[c.id,c]));
    for(const id of ordered(clips,selected,order)){
      const base=byId.get(id);
      const edit=edits[base.id]||base;
      if(!Number.isFinite(edit.start)||!Number.isFinite(edit.end)||edit.start<base.start||edit.end>base.end||edit.end<=edit.start)continue;
      const duration=edit.end-edit.start;
      ranges.push({id:base.id,start:edit.start,end:edit.end,offset:total,duration});
      total+=duration;
    }
    return {ranges,total};
  }
  function position(range,time){
    return range.offset+Math.max(0,Math.min(range.duration,time-range.start));
  }
  function locate(plan,time){
    if(!plan.ranges.length||!Number.isFinite(time))return null;
    const output=Math.max(0,Math.min(plan.total,time));
    const index=plan.ranges.findIndex(r=>output<r.offset+r.duration);
    const i=index<0?plan.ranges.length-1:index;
    const range=plan.ranges[i];
    return {index:i,source:Math.min(range.end,range.start+Math.max(0,output-range.offset)),output};
  }
  return Object.freeze({build,position,locate,ordered});
})();
