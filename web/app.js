"use strict";
const $ = id => document.getElementById(id);
const commands = ["project = import_media()", "metadata = probe_media(project)", "scenes = detect_scenes(project)", "timeline = build_timeline(scenes)", "render(selected_clips)"];
let token, job, clips = [], selected = new Set(), current = -1, busy = false, objectURL;
let visuals = new Map(), history = [], future = [];
function snapshot(){return [...selected];}
function remember(){history.push(snapshot());if(history.length>100)history.shift();future=[];}
function restore(stack, other){if(busy||!stack.length)return;other.push(snapshot());selected=new Set(stack.pop());$("download").hidden=true;drawTimeline();log("Selection history restored");}
function updatePlayhead(){
  const lane=$("tracks").querySelector(".lane");
  if(!lane||!job){$("playhead").hidden=true;return;}
  const parent=$("tracks").getBoundingClientRect(), bounds=lane.getBoundingClientRect();
  $("playhead").hidden=false;
  $("playhead").style.left=(bounds.left-parent.left+$("tracks").scrollLeft+Math.min(1,$("video").currentTime/job.duration)*bounds.width)+"px";
}
function waveform(peaks){
  const svg=document.createElementNS("http://www.w3.org/2000/svg","svg");
  svg.setAttribute("viewBox","0 0 "+Math.max(1,peaks.length*3)+" 40");
  svg.setAttribute("preserveAspectRatio","none");svg.classList.add("waveform");svg.setAttribute("aria-hidden","true");
  peaks.forEach((peak,i)=>{const bar=document.createElementNS(svg.namespaceURI,"line");const h=Math.max(.4,peak*18);bar.setAttribute("x1",i*3+1);bar.setAttribute("x2",i*3+1);bar.setAttribute("y1",20-h);bar.setAttribute("y2",20+h);svg.append(bar);});
  return svg;
}
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
  $("undo").disabled=busy||!history.length;$("redo").disabled=busy||!future.length;
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
        check.addEventListener("click",e=>e.stopPropagation());check.addEventListener("change",()=>{remember();check.checked?selected.add(clip.id):selected.delete(clip.id);$("download").hidden=true;drawTimeline();});cell.append(check);
      }
      const visual=visuals.get(clip.id);
      if(kind==="video"&&visual?.thumbnail){const img=document.createElement("img");img.src=visual.thumbnail;img.alt="";img.className="thumbnail";cell.prepend(img);}
      if(kind==="audio"&&visual?.peaks?.length)cell.prepend(waveform(visual.peaks));
      const name=document.createElement("span");name.textContent=kind==="audio"?"Audio "+(clip.id+1):"Scene "+(clip.id+1);cell.append(name);
      cell.tabIndex=0;cell.addEventListener("click",()=>preview(clip));cell.addEventListener("keydown",e=>{if(e.target===cell&&(e.key==="Enter"||e.key===" ")){e.preventDefault();preview(clip);}});lane.append(cell);
    }
    parent.append(row);
  }
  summary();updatePlayhead();
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
  job=result;clips=[];selected.clear();visuals.clear();history=[];future=[];current=-1;$("download").hidden=true;
  if(objectURL)URL.revokeObjectURL(objectURL);objectURL=URL.createObjectURL(file);$("video").src=objectURL;$("placeholder").hidden=true;$("project").textContent=file.name;
  $("format").textContent=job.width+" × "+job.height;step(1,true);log("Media verified · "+format(job.duration));
});$("file").value="";});
$("analyze").addEventListener("click",()=>action(async()=>{
  step(2);log("Running FFmpeg scene detection…");$("download").hidden=true;
  const result=await request("/api/analyze",{id:job.id});clips=result.clips;selected=new Set(clips.map(c=>c.id));visuals.clear();history=[];future=[];current=-1;
  step(3);log(clips.length+" scene segment(s) detected; extracting actual thumbnails and waveform");drawTimeline();
  try{const result=await request("/api/visuals",{id:job.id});visuals=new Map(result.visuals.map(v=>[v.id,v]));log("Scene thumbnails and source audio peaks ready");}
  catch(e){log("Visual extraction failed; cuts remain usable: "+e.message,true);}
  step(3,true);drawTimeline();connect(3,$("clip-0"));
}));
$("render").addEventListener("click",()=>action(async()=>{
  step(4);$("download").hidden=true;log("Rendering "+selected.size+" selected scenes…");
  const result=await request("/api/render",{id:job.id,clips:[...selected]});step(4,true);log("MP4 export complete");$("download").href=result.url;$("download").hidden=false;connect(4,$("download"));
}));
$("video").addEventListener("timeupdate",()=>{$("time").textContent=format($("video").currentTime);updatePlayhead();});
$("undo").addEventListener("click",()=>restore(history,future));
$("redo").addEventListener("click",()=>restore(future,history));
$("ticks").addEventListener("click",e=>{if(!job)return;const b=$("ticks").getBoundingClientRect();$("video").currentTime=Math.max(0,Math.min(job.duration,(e.clientX-b.left)/b.width*job.duration));updatePlayhead();});
window.addEventListener("resize",updatePlayhead);
$("tracks").addEventListener("scroll",updatePlayhead);
$("file").disabled=true;drawTimeline();
fetch("/api/session").then(r=>r.json()).then(data=>{token=data.token;updateButtons();log("Local processing engine ready");}).catch(()=>log("Unable to connect to local engine",true));
