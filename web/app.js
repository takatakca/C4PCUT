"use strict";
const $ = id => document.getElementById(id);
const commands = ["project = import_media()", "metadata = probe_media(project)", "scenes = detect_scenes(project)", "timeline = build_timeline(scenes)", "render(selected_clips)"];
let token, job, clips = [], selected = new Set(), current = -1, busy = false, objectURL;
const code = $("code");
commands.forEach(cmd => { const li = document.createElement("li"); li.textContent = cmd; code.append(li); });
const tracks = [["V3  EFFECTS","reserved"],["V2  CAPTIONS","reserved"],["V1  VIDEO","video"],["A1  SOURCE AUDIO","audio"],["A2  MUSIC","reserved"]];
function log(message, error=false) {
  const div = document.createElement("div");
  div.textContent = "[" + new Date().toLocaleTimeString() + "] " + message;
  if(error) div.className = "error";
  $("log").append(div); $("log").scrollTop = $("log").scrollHeight;
}
function step(index, done=false) {
  [...code.children].forEach((li,i) => li.className = i < index || (i===index && done) ? "done" : i===index ? "active" : "");
  $("progress").value = index + Number(done);
}
function updateButtons() {
  $("file").disabled = busy;
  $("analyze").disabled = busy || !job;
  $("render").disabled = busy || !selected.size;
  $("status").textContent = busy ? "● PROCESSING" : "● READY";
}
async function request(path, body, raw=false) {
  const response = await fetch(path,{method:"POST",headers:{"X-C4PCUT-Token":token,"Content-Type":raw?"application/octet-stream":"application/json"},body:raw?body:JSON.stringify(body)});
  const result = await response.json(); if(!response.ok) throw new Error(result.error); return result;
}
function format(t) { const m = Math.floor(t/60); return String(m).padStart(2,"0")+":"+String((t%60).toFixed(3)).padStart(6,"0"); }
function summary() {
  const seconds = clips.filter(c=>selected.has(c.id)).reduce((a,c)=>a+c.end-c.start,0);
  $("summary").textContent = selected.size+" / "+clips.length+" scenes selected · "+seconds.toFixed(2)+" s";
  updateButtons();
}
function drawTimeline() {
  const parent = $("tracks"); parent.querySelectorAll(".track").forEach(x=>x.remove());
  $("ticks").replaceChildren();
  for(let i=0;i<=5;i++){const s=document.createElement("span");s.textContent=format((job?.duration||0)*i/5);$("ticks").append(s);}
  for(const [label,kind] of tracks){
    const row=document.createElement("div");row.className="track";
    const title=document.createElement("span");title.textContent=label;row.append(title);
    const lane=document.createElement("div");lane.className="lane";row.append(lane);
    if(kind==="reserved" || !clips.length || (kind==="audio"&&!job.audio)){
      const empty=document.createElement("span");empty.className="empty";empty.textContent=kind==="reserved"?"Reserved for next milestone":kind==="audio"?"No source audio":"Analyze footage to populate";lane.append(empty);
    }else for(const clip of clips){
      const cell=document.createElement("div");cell.className="clip "+kind+(selected.has(clip.id)?"":" excluded")+(current===clip.id?" selected":"");
      cell.style.flex=(clip.end-clip.start)+" 1 0";cell.title=format(clip.start)+" – "+format(clip.end);
      if(kind==="video"){
        cell.id="clip-"+clip.id;const check=document.createElement("input");check.type="checkbox";check.checked=selected.has(clip.id);check.setAttribute("aria-label","Keep scene "+(clip.id+1));check.disabled=busy;
        check.addEventListener("click",e=>e.stopPropagation());check.addEventListener("change",()=>{check.checked?selected.add(clip.id):selected.delete(clip.id);$("download").hidden=true;drawTimeline();});cell.append(check);
      }
      const name=document.createElement("span");name.textContent=kind==="audio"?"Audio "+(clip.id+1):"Scene "+(clip.id+1);cell.append(name);
      cell.tabIndex=0;cell.addEventListener("click",()=>preview(clip));cell.addEventListener("keydown",e=>{if(e.target===cell&&(e.key==="Enter"||e.key===" ")){e.preventDefault();preview(clip);}});lane.append(cell);
    }
    parent.append(row);
  }
  summary();
}
function preview(clip){current=clip.id;$("video").currentTime=clip.start;$("selection").textContent="Scene "+(clip.id+1)+" · "+format(clip.start);drawTimeline();connect(3,$("clip-"+clip.id));}
let connectionTimer;
function connect(line,target){
  if(!target)return; const svg=$("connections"), base=$("studio").getBoundingClientRect(), a=code.children[line].getBoundingClientRect(), b=target.getBoundingClientRect();
  const x=a.right-base.left-15,y=a.top-base.top+a.height/2,tx=b.left-base.left+b.width/2,ty=b.top-base.top+3;
  const p=document.createElementNS("http://www.w3.org/2000/svg","path");p.setAttribute("d","M"+x+" "+y+" C"+x+" "+(ty-35)+" "+tx+" "+(y+30)+" "+tx+" "+ty);p.setAttribute("stroke","#b48aff");svg.replaceChildren(p);clearTimeout(connectionTimer);connectionTimer=setTimeout(()=>svg.replaceChildren(),2000);
}
async function action(fn){
  if(busy)return;busy=true;updateButtons();drawTimeline();try{await fn();}catch(e){log(e.message,true);}finally{busy=false;drawTimeline();}
}
$("file").addEventListener("change",()=>{const file=$("file").files[0];if(!file)return;action(async()=>{
  if(file.size>250*1024*1024)throw new Error("Maximum input size is 250 MB");
  step(0);log("Importing "+file.name);const result=await request("/api/import",file,true);
  job=result;clips=[];selected.clear();current=-1;$("download").hidden=true;
  if(objectURL)URL.revokeObjectURL(objectURL);objectURL=URL.createObjectURL(file);$("video").src=objectURL;$("placeholder").hidden=true;$("project").textContent=file.name;
  $("format").textContent=job.width+" × "+job.height;step(1,true);log("Media verified · "+format(job.duration));
});$("file").value="";});
$("analyze").addEventListener("click",()=>action(async()=>{
  step(2);log("Running FFmpeg scene detection…");$("download").hidden=true;
  const result=await request("/api/analyze",{id:job.id});clips=result.clips;selected=new Set(clips.map(c=>c.id));current=-1;
  step(3,true);log(clips.length+" scene segment(s) detected and added to timeline");drawTimeline();connect(3,$("clip-0"));
}));
$("render").addEventListener("click",()=>action(async()=>{
  step(4);$("download").hidden=true;log("Rendering "+selected.size+" selected scenes…");
  const result=await request("/api/render",{id:job.id,clips:[...selected]});step(4,true);log("MP4 export complete");$("download").href=result.url;$("download").hidden=false;connect(4,$("download"));
}));
$("video").addEventListener("timeupdate",()=>{$("time").textContent=format($("video").currentTime);});
$("file").disabled=true;drawTimeline();
fetch("/api/session").then(r=>r.json()).then(data=>{token=data.token;updateButtons();log("Local processing engine ready");}).catch(()=>log("Unable to connect to local engine",true));
