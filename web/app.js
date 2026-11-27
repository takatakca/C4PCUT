"use strict";
const $ = id => document.getElementById(id);
const commands = ["project = import_media()", "metadata = probe_media(project)", "scenes = detect_scenes(project)", "timeline = build_timeline(scenes)", "render(selected_clips)"];
let token, job, clips = [], selected = new Set(), current = -1, busy = false, objectURL;
let visuals = new Map(), history = [], future = [], edits = {}, cues = [], activeCue = -1;
let musicData=null, sourceBeats=null, musicName="";
function beatData(){return $("use-music").checked?musicData:sourceBeats;}
function resetMusic(){musicData=null;sourceBeats=null;musicName="";$("use-music").checked=false;$("music-gain").value=.35;$("source-gain").value=1;}
function musicStatus(){const data=beatData();$("beat-info").textContent=data?data.beats.length+" detected onsets"+(data.estimated_bpm?" · ~"+data.estimated_bpm+" BPM estimate":""):"No beat analysis";}
function snapshot(){return {selected:[...selected],edits:JSON.parse(JSON.stringify(edits)),cues:JSON.parse(JSON.stringify(cues))};}
function hideExports(){$("download").hidden=true;$("download-srt").hidden=true;}
function edited(c){return edits[c.id]||c;}
function remember(){history.push(snapshot());if(history.length>100)history.shift();future=[];}
function restore(stack, other){if(busy||!stack.length)return;other.push(snapshot());const state=stack.pop();selected=new Set(state.selected);edits=state.edits;cues=state.cues;activeCue=-1;refreshCaption();refreshInspector();hideExports();drawTimeline();log("Selection history restored");}
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
const tracks = [["V3  EFFECTS","effect"],["V2  CAPTIONS","caption"],["V1  VIDEO","video"],["A1  SOURCE AUDIO","audio"],["A2  MUSIC","music"]];
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
  for(const id of ["trim-in","trim-out","effect","apply-edit","reset-edit"])$(id).disabled=busy||current<0;
  $("srt-file").disabled=busy||!job;$("transcribe").disabled=busy||!job?.audio;$("clear-captions").disabled=busy||!cues.length;$("caption-text").disabled=busy||activeCue<0;$("apply-caption").disabled=busy||activeCue<0;
  $("music-file").disabled=busy||!job;$("use-music").disabled=busy||!musicData;$("music-gain").disabled=busy||!$("use-music").checked;$("source-gain").disabled=busy||!job?.audio;
  $("detect-beats").disabled=busy||!job||(!job.audio&&!$("use-music").checked);$("beat-interval").disabled=busy||!beatData()?.beats.length;$("beat-cut").disabled=busy||!beatData()?.beats.length;musicStatus();
  $("status").textContent = busy ? "● PROCESSING" : "● READY";
}
async function request(path, body, raw=false) {
  const response = await fetch(path,{method:"POST",headers:{"X-C4PCUT-Token":token,"Content-Type":raw?"application/octet-stream":"application/json"},body:raw?body:JSON.stringify(body)});
  const result = await response.json(); if(!response.ok) throw new Error(result.error); return result;
}
function format(t) { const m = Math.floor(t/60); return String(m).padStart(2,"0")+":"+String((t%60).toFixed(3)).padStart(6,"0"); }
function summary() {
  const seconds = clips.filter(c=>selected.has(c.id)).reduce((a,c)=>a+edited(c).end-edited(c).start,0);
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
    if(kind==="music"){
      lane.classList.add("music-lane");
      const data=beatData();
      if(data){
        if($("use-music").checked&&data.peaks.length)lane.append(waveform(data.peaks));
        data.beats.forEach(t=>{const marker=document.createElement("span");marker.className="beat-marker";marker.style.left=(t/job.duration*100)+"%";marker.title=format(t);lane.append(marker);});
      }
      const label=document.createElement("span");label.className="music-label";label.textContent=$("use-music").checked?musicName:data?"Source audio onset guide":"Import music or analyze source audio";lane.append(label);
    }else if(kind==="caption"){
      lane.classList.add("caption-lane");
      if(!cues.length){const msg=document.createElement("span");msg.className="empty";msg.textContent="Import SRT or generate local AI captions";lane.append(msg);}
      cues.forEach((cue,i)=>{const item=document.createElement("button");item.className="caption-block"+(i===activeCue?" selected":"");item.style.left=(cue.start/job.duration*100)+"%";item.style.width=((cue.end-cue.start)/job.duration*100)+"%";item.textContent=cue.text;item.title=cue.text;item.disabled=busy;item.addEventListener("click",()=>{activeCue=i;$("video").currentTime=cue.start;refreshCaption();drawTimeline();connect(3,item);});lane.append(item);});
    }else if(kind==="reserved" || !clips.length || (kind==="audio"&&!job.audio)){
      const empty=document.createElement("span");empty.className="empty";empty.textContent=kind==="reserved"?"Reserved for next milestone":kind==="audio"?"No source audio":"Analyze footage to populate";lane.append(empty);
    }else for(const clip of clips){
      const cell=document.createElement("div");cell.className="clip "+kind+(selected.has(clip.id)?"":" excluded")+(current===clip.id?" selected":"");
      cell.style.flex=(clip.end-clip.start)+" 1 0";const edit=edited(clip);cell.title=format(edit.start)+" – "+format(edit.end);
      if(kind==="effect"){cell.classList.add(edit.effect&&edit.effect!=="none"?"effect-on":"effect-off");}
      if(kind==="video"&&(edit.start!==clip.start||edit.end!==clip.end)){
        const shade=document.createElement("div");shade.className="trim-overlay";shade.style.setProperty("--in",((edit.start-clip.start)/(clip.end-clip.start)*100)+"%");shade.style.setProperty("--out",((clip.end-edit.end)/(clip.end-clip.start)*100)+"%");cell.append(shade);
      }
      if(kind==="video"){
        cell.id="clip-"+clip.id;const check=document.createElement("input");check.type="checkbox";check.checked=selected.has(clip.id);check.setAttribute("aria-label","Keep scene "+(clip.id+1));check.disabled=busy;
        check.addEventListener("click",e=>e.stopPropagation());check.addEventListener("change",()=>{remember();check.checked?selected.add(clip.id):selected.delete(clip.id);hideExports();drawTimeline();});cell.append(check);
      }
      const visual=visuals.get(clip.id);
      if(kind==="video"&&visual?.thumbnail){const img=document.createElement("img");img.src=visual.thumbnail;img.alt="";img.className="thumbnail";cell.prepend(img);}
      if(kind==="audio"&&visual?.peaks?.length)cell.prepend(waveform(visual.peaks));
      const name=document.createElement("span");name.textContent=kind==="effect"?(edit.effect&&edit.effect!=="none"?edit.effect:"—"):kind==="audio"?"Audio "+(clip.id+1):"Scene "+(clip.id+1);cell.append(name);
      cell.tabIndex=0;cell.addEventListener("click",()=>preview(clip));cell.addEventListener("keydown",e=>{if(e.target===cell&&(e.key==="Enter"||e.key===" ")){e.preventDefault();preview(clip);}});lane.append(cell);
    }
    parent.append(row);
  }
  summary();updatePlayhead();updateCaptionOverlay();
}
function refreshInspector(){
  const base=clips.find(c=>c.id===current);if(!base)return;
  const c=edited(base);$("trim-in").min=base.start;$("trim-in").max=base.end;$("trim-out").min=base.start;$("trim-out").max=base.end;
  $("trim-in").value=c.start;$("trim-out").value=c.end;$("effect").value=c.effect||"none";
  $("selection").textContent="Scene "+(base.id+1)+" · source preview";
}
function preview(clip){current=clip.id;$("video").currentTime=edited(clip).start;refreshInspector();drawTimeline();connect(3,$("clip-"+clip.id));}
$("apply-edit").addEventListener("click",()=>{
  const base=clips.find(c=>c.id===current);if(!base||busy)return;
  const start=$("trim-in").valueAsNumber,end=$("trim-out").valueAsNumber,effect=$("effect").value;
  if(!Number.isFinite(start)||!Number.isFinite(end)||start<base.start||end>base.end||end<=start||end-start<Math.min(.1,base.end-base.start)-1e-9){log("Trim must stay within scene boundaries",true);return;}
  remember();edits[base.id]={start,end,effect};hideExports();drawTimeline();log("Applied scene "+(base.id+1)+" trim / "+effect);connect(3,$("clip-"+base.id));
});
$("reset-edit").addEventListener("click",()=>{if(busy||current<0||!edits[current])return;remember();delete edits[current];hideExports();refreshInspector();drawTimeline();log("Scene edit reset");});
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
  job=result;resetMusic();clips=[];cues=[];activeCue=-1;refreshCaption();selected.clear();visuals.clear();history=[];future=[];edits={};current=-1;hideExports();
  if(objectURL)URL.revokeObjectURL(objectURL);objectURL=URL.createObjectURL(file);$("video").src=objectURL;$("placeholder").hidden=true;$("project").textContent=file.name;
  $("format").textContent=job.width+" × "+job.height;step(1,true);log("Media verified · "+format(job.duration));
});$("file").value="";});
$("analyze").addEventListener("click",()=>action(async()=>{
  step(2);log("Running FFmpeg scene detection…");hideExports();
  const result=await request("/api/analyze",{id:job.id});clips=result.clips;selected=new Set(clips.map(c=>c.id));visuals.clear();history=[];future=[];edits={};current=-1;
  step(3);log(clips.length+" scene segment(s) detected; extracting actual thumbnails and waveform");drawTimeline();
  try{const result=await request("/api/visuals",{id:job.id});visuals=new Map(result.visuals.map(v=>[v.id,v]));log("Scene thumbnails and source audio peaks ready");}
  catch(e){log("Visual extraction failed; cuts remain usable: "+e.message,true);}
  step(3,true);drawTimeline();connect(3,$("clip-0"));
}));
$("render").addEventListener("click",()=>action(async()=>{
  step(4);hideExports();log("Rendering "+selected.size+" selected scenes…");
  const result=await request("/api/render",{id:job.id,clips:[...selected],edits,cues,use_music:$("use-music").checked,music_gain:Number($("music-gain").value),source_gain:Number($("source-gain").value)});step(4,true);log("MP4 export complete");$("download").href=result.url;$("download").hidden=false;if(result.captions_url){$("download-srt").href=result.captions_url;$("download-srt").hidden=false;}connect(4,$("download"));
}));
$("video").addEventListener("timeupdate",()=>{$("time").textContent=format($("video").currentTime);updatePlayhead();updateCaptionOverlay();});
$("undo").addEventListener("click",()=>restore(history,future));
$("redo").addEventListener("click",()=>restore(future,history));
$("ticks").addEventListener("click",e=>{if(!job)return;const b=$("ticks").getBoundingClientRect();$("video").currentTime=Math.max(0,Math.min(job.duration,(e.clientX-b.left)/b.width*job.duration));updatePlayhead();});
window.addEventListener("resize",updatePlayhead);
$("tracks").addEventListener("scroll",updatePlayhead);
$("file").disabled=true;drawTimeline();
fetch("/api/session").then(r=>r.json()).then(data=>{token=data.token;updateButtons();log("Local processing engine ready");}).catch(()=>log("Unable to connect to local engine",true));

function refreshCaption(){$("caption-text").value=cues[activeCue]?.text||"";}
function updateCaptionOverlay(){
  const now=$("video").currentTime;
  const text=cues.filter(c=>c.start<=now&&now<c.end).map(c=>c.text).join("\n");
  $("caption-overlay").textContent=text;$("caption-overlay").hidden=!text;
}
function installCues(next){remember();cues=next;activeCue=-1;refreshCaption();hideExports();drawTimeline();log(cues.length+" source-time captions loaded");}
$("srt-file").addEventListener("change",()=>{const file=$("srt-file").files[0];$("srt-file").value="";if(!file)return;action(async()=>{if(file.size>200000)throw new Error("SRT too large");const result=await request("/api/captions/import",{id:job.id,srt:await file.text()});installCues(result.cues);});});
$("transcribe").addEventListener("click",()=>action(async()=>{log("Running local speech recognition…");const result=await request("/api/transcribe",{id:job.id});installCues(result.cues);}));
$("clear-captions").addEventListener("click",()=>{if(!busy)installCues([]);});
$("apply-caption").addEventListener("click",()=>{if(busy||activeCue<0)return;const text=$("caption-text").value.trim();if(!text){log("Caption text cannot be empty",true);return;}remember();cues[activeCue]={...cues[activeCue],text};hideExports();drawTimeline();log("Caption text updated");});

$("music-file").addEventListener("change",()=>{const file=$("music-file").files[0];$("music-file").value="";if(!file)return;action(async()=>{
  if(file.size>64*1024*1024)throw new Error("Maximum music upload is 64 MB");
  log("Decoding music and detecting audio onsets…");
  const result=await request("/api/music/import/"+job.id,file,true);musicData=result;musicName=file.name;$("use-music").checked=true;hideExports();drawTimeline();log(result.beats.length+" music onsets detected");
});});
$("use-music").addEventListener("change",()=>{hideExports();drawTimeline();});
for(const id of ["music-gain","source-gain"])$(id).addEventListener("input",hideExports);
$("detect-beats").addEventListener("click",()=>action(async()=>{
  log("Analyzing audio transients…");const use_music=$("use-music").checked;
  const result=await request("/api/music/analyze",{id:job.id,use_music});if(use_music)musicData=result;else sourceBeats=result;
  drawTimeline();log(result.beats.length+" onset markers available");
}));
$("beat-cut").addEventListener("click",()=>{
  if(busy||!beatData()?.beats.length)return;
  if(clips.length&&!window.confirm("Replace existing scene cuts, trims, and effects? Captions and music stay."))return;
  action(async()=>{
    log("Building a new cut sequence from detected onsets…");hideExports();
    const result=await request("/api/music/cuts",{id:job.id,use_music:$("use-music").checked,interval:Number($("beat-interval").value)});
    clips=result.clips;selected=new Set(clips.map(c=>c.id));visuals.clear();history=[];future=[];edits={};current=-1;drawTimeline();
    try{const result=await request("/api/visuals",{id:job.id});visuals=new Map(result.visuals.map(v=>[v.id,v]));}catch(e){log("Visual extraction failed: "+e.message,true);}
    drawTimeline();log(clips.length+" beat-based segments created");connect(3,$("clip-0"));
  });
});
