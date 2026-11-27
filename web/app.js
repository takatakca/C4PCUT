"use strict";
const $ = id => document.getElementById(id);
const commands = ["project = import_media()", "metadata = probe_media(project)", "scenes = detect_scenes(project)", "timeline = build_timeline(scenes)", "render(selected_clips)"];
let token, job, clips = [], selected = new Set(), current = -1, busy = false, objectURL, sourceMime="", activeRender=null, studioBrief=null;
let visuals = new Map(), history = [], future = [], edits = {}, cues = [], activeCue = -1;
let musicData=null, sourceBeats=null, musicName="", directorPlan=null;
let account=null, accountRefreshing=false, accountInvalid=false, projectCount=null, usageState=null;
const canFeature=name=>!!account&&!accountInvalid&&PlanUI.feature(account.capabilities,name);
let clipBatch=null, clipCandidates=[], clipDownloads=new Map();
let sequence=null, sequenceFrame=0, sequenceSeek=null, monitorURL=null, monitorPending=false, monitorGeneration=0;
function clearMonitorMusic(){
  monitorGeneration++;
  const audio=$("monitor-audio");audio.pause();audio.removeAttribute("src");audio.load();
  if(monitorURL)URL.revokeObjectURL(monitorURL);monitorURL=null;monitorPending=false;
  $("monitor-mix").textContent="No soundtrack loaded";
}
async function loadMonitorMusic(){
  clearMonitorMusic();
  if(!job||!musicData||!canFeature("music"))return;
  const id=job.id,generation=monitorGeneration;
  $("monitor-mix").textContent="Loading normalized soundtrack…";
  try{
    const response=await fetch("/api/soundtrack/"+id,{cache:"no-store"});
    if(!response.ok)throw new Error("Soundtrack unavailable");
    const blob=await response.blob();
    if(job?.id!==id||generation!==monitorGeneration||!canFeature("music"))return;
    // Normalized stereo 48kHz PCM, at most 600 seconds plus WAV header.
    if(!blob.size||blob.size>116000000)throw new Error("Soundtrack too large");
    monitorURL=URL.createObjectURL(blob);$("monitor-audio").src=monitorURL;
    $("monitor-mix").textContent="Soundtrack ready · source-time alignment";
  }catch(e){if(generation===monitorGeneration)$("monitor-mix").textContent="Soundtrack preview unavailable; export unchanged";}
}
function pauseMonitor(){ $("monitor-audio").pause(); }
function syncMonitor(force=false){
  const video=$("video"), audio=$("monitor-audio"), state=sequence;
  if(!state)return;
  const gain=Number($("source-gain").value);
  if(video.volume!==gain)video.volume=gain;
  if(!state.mix||!canFeature("music")||!monitorURL||video.paused||video.seeking||sequenceSeek!==null||video.readyState<3){pauseMonitor();return;}
  audio.volume=Number($("music-gain").value);audio.muted=video.muted;audio.playbackRate=video.playbackRate;
  if(audio.readyState<1||!Number.isFinite(audio.duration)||video.currentTime>=audio.duration){pauseMonitor();return;}
  if(force||Math.abs(audio.currentTime-video.currentTime)>.15)audio.currentTime=video.currentTime;
  if(audio.paused&&!monitorPending){
    const generation=monitorGeneration;
    monitorPending=true;audio.play().then(()=>{if(generation===monitorGeneration&&(sequence!==state||video.paused||video.seeking||sequenceSeek!==null))audio.pause();}).catch(error=>{if(generation===monitorGeneration&&sequence===state&&error.name!=="AbortError"){state.mix=false;$("monitor-mix").textContent="Music playback unavailable; source audio continues";}}).finally(()=>{if(generation===monitorGeneration)monitorPending=false;});
  }
}
$("monitor-audio").addEventListener("loadedmetadata",()=>{if(sequence)syncMonitor(true);});
$("video").addEventListener("waiting",pauseMonitor);
$("video").addEventListener("ratechange",()=>syncMonitor(true));
$("video").addEventListener("volumechange",()=>{if(sequence)$("monitor-audio").muted=$("video").muted;});
let sceneOrder=[];
function selectedOrder(){return SequencePreview.ordered(clips,selected,sceneOrder);}
function moveScene(from,to){
  const order=selectedOrder(),i=order.indexOf(from),j=order.indexOf(to);
  if(busy||i<0||j<0||i===j)return;
  remember();order.splice(i,1);order.splice(j,0,from);sceneOrder=order;hideExports();showSequencePosition(0,sequencePlan().total);drawTimeline();
  log("Scene "+(from+1)+" moved to position "+(j+1));
}
function drawSceneOrder(){
  const list=$("scene-order"),order=selectedOrder();list.replaceChildren();
  if(!order.length){list.textContent="Select scenes to arrange the edited sequence.";return;}
  order.forEach((id,i)=>{
    const card=document.createElement("div");card.className="order-card";card.draggable=!busy;card.dataset.scene=String(id);
    const label=document.createElement("span");label.textContent=(i+1)+". Scene "+(id+1);card.append(label);
    for(const [direction,target] of [["Earlier",order[i-1]],["Later",order[i+1]]]){
      const b=document.createElement("button");b.textContent=direction==="Earlier"?"←":"→";b.setAttribute("aria-label",direction+" scene "+(id+1));b.disabled=busy||target===undefined;b.onclick=()=>moveScene(id,target);card.append(b);
    }
    card.addEventListener("dragstart",e=>{if(busy){e.preventDefault();return;}e.dataTransfer.setData("application/x-c4pcut-scene",String(id));e.dataTransfer.effectAllowed="move";});
    card.addEventListener("dragover",e=>{if(!busy&&e.dataTransfer.types.includes("application/x-c4pcut-scene")){e.preventDefault();e.dataTransfer.dropEffect="move";}});
    card.addEventListener("drop",e=>{e.preventDefault();const raw=e.dataTransfer.getData("application/x-c4pcut-scene");if(/^\d{1,2}$/.test(raw))moveScene(Number(raw),id);});
    list.append(card);
  });
}
$("reset-order").addEventListener("click",()=>{if(busy)return;const order=selectedOrder();if(order.every((id,i)=>i===0||id>order[i-1]))return;remember();sceneOrder=[];hideExports();showSequencePosition(0,sequencePlan().total);drawTimeline();});
function sequencePlan(){return SequencePreview.build(clips,edits,selected,selectedOrder());}
function showSequencePosition(value,total){
  const bar=$("sequence-position");bar.max=String(total);bar.value=String(Math.max(0,Math.min(total,value)));
  $("sequence-clock").textContent=format(value)+" / "+format(total);
}
function stopSequence(completed=false){
  const prior=sequence;sequence=null;sequenceSeek=null;
  if(sequenceFrame)cancelAnimationFrame(sequenceFrame);sequenceFrame=0;
  pauseMonitor();
  if(prior){$("video").pause();$("video").volume=prior.previousVolume;if(completed)showSequencePosition(prior.plan.total,prior.plan.total);}
  $("stop-sequence").disabled=true;
  $("sequence-note").textContent=completed?"Sequence complete · approximate preview":"Approximate cuts and audio preview";
}
function queueSequenceFrame(){if(sequence&&!sequenceFrame)sequenceFrame=requestAnimationFrame(sequenceTick);}
function seekSequence(time){
  const video=$("video");
  if(Math.abs(video.currentTime-time)<.001&&!video.seeking){sequenceSeek=null;return;}
  pauseMonitor();sequenceSeek=time;video.currentTime=time;
}
async function playSequenceFrom(time){
  const video=$("video"),plan=sequencePlan();
  if(busy||!job||!plan.total||video.readyState<1)return;
  stopSequence();
  const target=SequencePreview.locate(plan,time>=plan.total?0:time);
  if(!target)return;
  const state={plan,index:target.index,mix:!!(monitorURL&&$("use-music").checked&&canFeature("music")),previousVolume:video.volume};sequence=state;
  $("stop-sequence").disabled=false;
  $("sequence-note").textContent=state.mix?"Playing selected trims · approximate audio mix":"Playing selected trims · source audio";
  video.volume=Number($("source-gain").value);
  showSequencePosition(target.output,plan.total);
  seekSequence(target.source);
  try{await video.play();if(sequence===state){syncMonitor(true);queueSequenceFrame();}}
  catch(e){if(sequence===state){stopSequence();log("Sequence playback unavailable",true);}}
}
function sequenceTick(){
  sequenceFrame=0;
  const state=sequence,video=$("video");if(!state)return;
  if(video.seeking||sequenceSeek!==null){pauseMonitor();queueSequenceFrame();return;}
  const range=state.plan.ranges[state.index],time=video.currentTime;
  if(time>=range.end||video.ended){
    if(state.index+1>=state.plan.ranges.length){stopSequence(true);return;}
    const next=state.plan.ranges[++state.index];showSequencePosition(next.offset,state.plan.total);
    seekSequence(next.start);
    if(video.paused)video.play().catch(()=>{if(sequence===state)stopSequence();});
  }else if(time<range.start-.05){stopSequence();return;}
  else {showSequencePosition(SequencePreview.position(range,time),state.plan.total);syncMonitor();}
  queueSequenceFrame();
}
$("play-sequence").addEventListener("click",()=>playSequenceFrom(Number($("sequence-position").value)));
$("stop-sequence").addEventListener("click",()=>stopSequence());
$("sequence-position").addEventListener("input",()=>{
  const time=Number($("sequence-position").value),plan=sequencePlan(),target=SequencePreview.locate(plan,time);
  if(!target)return;stopSequence();$("video").currentTime=target.source;showSequencePosition(target.output,plan.total);
});
$("video").addEventListener("seeking",()=>{
  if(sequence&&sequenceSeek===null)stopSequence();
});
$("video").addEventListener("seeked",()=>{
  if(sequence&&sequenceSeek!==null){if(Math.abs($("video").currentTime-sequenceSeek)>.15){stopSequence();return;}sequenceSeek=null;syncMonitor(true);queueSequenceFrame();}
});
$("video").addEventListener("pause",()=>{if(sequence&&!$("video").ended&&sequenceSeek===null)stopSequence();});
$("video").addEventListener("ended",()=>{if(sequence)queueSequenceFrame();});
$("video").addEventListener("error",()=>stopSequence());
$("video").addEventListener("emptied",()=>stopSequence());
document.addEventListener("visibilitychange",()=>{if(document.hidden)stopSequence();});
function clearClipper(){clipBatch=null;clipCandidates=[];clipDownloads.clear();$("clipper-results").replaceChildren();$("clipper-status").textContent="No current suggestions";}
function clipperButtons(){
  $("clipper-suggest").disabled=busy||!clips.length||!canFeature("clipper");
  $("clipper-render-all").disabled=busy||!clipBatch||!clipCandidates.length||!canFeature("clipper");
  for(const id of ["clipper-target","clipper-count","clipper-style"])$(id).disabled=busy||!canFeature("clipper");
  $("clipper-results").querySelectorAll("button").forEach(b=>b.disabled=busy||!canFeature("clipper"));
}
function clipperSettings(){return {cues,caption_mode:$("caption-mode").value,preset:$("export-preset").value,framing:$("export-framing").value,quality:$("export-quality").value,use_music:$("use-music").checked,music_gain:Number($("music-gain").value),source_gain:Number($("source-gain").value)};}
function drawClipper(){
  const parent=$("clipper-results");parent.replaceChildren();
  for(const c of clipCandidates){
    const card=document.createElement("div");card.className="clipper-card";
    const title=document.createElement("strong");title.textContent="Clip "+(c.id+1)+" · "+c.duration.toFixed(1)+"s";card.append(title);
    const detail=document.createElement("small");detail.textContent=format(c.start)+" – "+format(c.end)+" · "+c.onsets+" onsets";card.append(detail);
    const row=document.createElement("div");row.className="clipper-actions";
    const preview=document.createElement("button");preview.textContent="Preview source";preview.onclick=()=>{stopSequence();$("video").currentTime=c.start;};row.append(preview);
    const render=document.createElement("button");render.textContent="Render";render.onclick=()=>action(async()=>{await renderClip(c);});row.append(render);
    if(clipDownloads.has(c.id)){const a=document.createElement("a");a.href=clipDownloads.get(c.id);a.textContent="Download MP4";a.download="c4pcut-clip-"+(c.id+1)+".mp4";row.append(a);}
    card.append(row);parent.append(card);
  }
  clipperButtons();
}
async function renderClip(c){
  log("Rendering promotional clip "+(c.id+1)+"…");
  const result=await request("/api/clipper/render",{id:job.id,batch:clipBatch,index:c.id,...clipperSettings()});
  clipDownloads.set(c.id,result.url);drawClipper();log("Promotional clip "+(c.id+1)+" ready");
}
function clearDirector(){directorPlan=null;$("director-result").textContent="No pending plan";}
function beatData(){return $("use-music").checked?musicData:sourceBeats;}
function resetMusic(){clearMonitorMusic();musicData=null;sourceBeats=null;musicName="";$("use-music").checked=false;$("music-gain").value=.35;$("source-gain").value=1;}
function musicStatus(){const data=beatData();$("beat-info").textContent=data?data.beats.length+" detected onsets"+(data.estimated_bpm?" · ~"+data.estimated_bpm+" BPM estimate":""):"No beat analysis";}
function snapshot(){return {selected:[...selected],order:selectedOrder(),edits:JSON.parse(JSON.stringify(edits)),cues:JSON.parse(JSON.stringify(cues))};}
function hideExports(){stopSequence();$("download").hidden=true;$("download-srt").hidden=true;}
function edited(c){return edits[c.id]||c;}
function remember(){history.push(snapshot());if(history.length>100)history.shift();future=[];}
function restore(stack, other){if(busy||!stack.length)return;other.push(snapshot());const state=stack.pop();selected=new Set(state.selected);sceneOrder=state.order||[];edits=state.edits;cues=state.cues;activeCue=-1;refreshCaption();refreshInspector();hideExports();drawTimeline();log("Selection history restored");}
function updateEffectPreview(){
  const video=$("video"), enabled=!!job&&$("preview-effects").checked;
  const state=EffectPreview.at(clips,edits,selected,video.currentTime,enabled);
  video.style.filter=state.filter;
  video.style.transform=state.scale===1?"none":"scale("+state.scale.toFixed(4)+")";
  video.dataset.previewEffect=state.effect;
  $("preview-effect-label").textContent=!enabled?"Source footage · no export preview":state.effect==="none"?"Approximate effects · source time":"Approximate "+state.effect+" preview · source time";
}
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
  $("preview-effects").disabled=!job||!clips.length;
  const plan=sequencePlan();
  $("play-sequence").disabled=busy||!job||!plan.total||$("video").readyState<1;
  $("sequence-position").disabled=busy||!job||!plan.total||$("video").readyState<1;
  if(!sequence)showSequencePosition(Math.min(Number($("sequence-position").value)||0,plan.total),plan.total);
  $("analyze").disabled = busy || !job;
  $("render").disabled = busy || !selected.size;
  $("studio-pack").disabled=busy||!job;
  $("clear-studio-brief").disabled=busy||!studioBrief;
  $("export-quality").disabled=busy;$("cancel-render").disabled=!activeRender;
  $("save-project").disabled=busy||!job;
  $("open-project").disabled=busy||!$("saved-projects").value||$("saved-projects").selectedOptions[0]?.dataset.saved!=="true";
  $("delete-project").disabled=busy||(!job&&!$("saved-projects").value);
  $("project-name").disabled=busy;$("saved-projects").disabled=busy;
  $("export-preset").disabled=busy;$("export-framing").disabled=busy||$("export-preset").value==="original";
  clipperButtons();
  $("director-plan").disabled=busy||!clips.length;
  $("director-apply").disabled=busy||!directorPlan;
  $("cinematic").disabled=busy||!selected.size;
  $("undo").disabled=busy||!history.length;$("redo").disabled=busy||!future.length;
  for(const id of ["trim-in","trim-out","effect","apply-edit","reset-edit"])$(id).disabled=busy||current<0;
  $("srt-file").disabled=busy||!job;$("transcribe").disabled=busy||!job?.audio;$("clear-captions").disabled=busy||!cues.length;$("caption-mode").disabled=busy||!cues.length;$("caption-text").disabled=busy||activeCue<0;$("apply-caption").disabled=busy||activeCue<0;
  $("music-file").disabled=busy||!job;$("use-music").disabled=busy||!musicData;$("music-gain").disabled=busy||!$("use-music").checked;$("source-gain").disabled=busy||!job?.audio;
  $("detect-beats").disabled=busy||!job||(!job.audio&&!$("use-music").checked);$("beat-interval").disabled=busy||!beatData()?.beats.length;$("beat-cut").disabled=busy||!beatData()?.beats.length;musicStatus();
  applyAccountControls();
  $("status").textContent = accountInvalid?"● RECONNECT":busy ? "● PROCESSING" : "● READY";
}
async function request(path, body, raw=false) {
  if(!token||accountInvalid)throw new Error("Reconnect before editing");
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
      cues.forEach((cue,i)=>{const item=document.createElement("button");item.className="caption-block"+(i===activeCue?" selected":"");item.style.left=(cue.start/job.duration*100)+"%";item.style.width=((cue.end-cue.start)/job.duration*100)+"%";item.textContent=cue.text;item.title=cue.text;item.disabled=busy;item.addEventListener("click",()=>{activeCue=i;stopSequence();$("video").currentTime=cue.start;refreshCaption();drawTimeline();connect(3,item);});lane.append(item);});
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
  drawSceneOrder();$("reset-order").disabled=busy||selected.size<2;
  summary();updatePlayhead();updateCaptionOverlay();updateEffectPreview();
}
function refreshInspector(){
  const base=clips.find(c=>c.id===current);if(!base)return;
  const c=edited(base);$("trim-in").min=base.start;$("trim-in").max=base.end;$("trim-out").min=base.start;$("trim-out").max=base.end;
  $("trim-in").value=c.start;$("trim-out").value=c.end;$("effect").value=c.effect||"none";
  $("selection").textContent="Scene "+(base.id+1)+" · source preview";
}
function preview(clip){stopSequence();current=clip.id;$("video").currentTime=edited(clip).start;refreshInspector();drawTimeline();connect(3,$("clip-"+clip.id));}
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
  if(busy||accountRefreshing||!token||accountInvalid)return;stopSequence();busy=true;updateButtons();drawTimeline();try{await fn();}catch(e){log(e.message,true);}finally{busy=false;drawTimeline();refreshUsage();}
}
$("file").addEventListener("change",()=>{const file=$("file").files[0];if(!file)return;action(async()=>{
  if(file.size>250*1024*1024)throw new Error("Maximum input size is 250 MB");
  step(0);log("Importing "+file.name);const result=await request("/api/import",file,true);
  showSequencePosition(0,0);job=result;if(projectCount!==null)projectCount++;setStudioBrief(null);sourceMime=["video/mp4","video/quicktime","video/webm"].includes(file.type)?file.type:"";$("saved-projects").value="";clearDirector();clearClipper();resetMusic();clips=[];cues=[];$("caption-mode").value="soft";activeCue=-1;refreshCaption();selected.clear();sceneOrder=[];visuals.clear();history=[];future=[];edits={};current=-1;hideExports();
  if(objectURL)URL.revokeObjectURL(objectURL);objectURL=URL.createObjectURL(file);$("video").src=objectURL;$("placeholder").hidden=true;$("project").textContent=file.name;$("project-name").value=file.name.slice(0,160);
  $("format").textContent=job.width+" × "+job.height;step(1,true);log("Media verified · "+format(job.duration));
});$("file").value="";});
$("analyze").addEventListener("click",()=>action(async()=>{
  step(2);log("Running FFmpeg scene detection…");hideExports();
  const result=await request("/api/analyze",{id:job.id});clearDirector();clearClipper();clips=result.clips;selected=new Set(clips.map(c=>c.id));sceneOrder=[];visuals.clear();history=[];future=[];edits={};current=-1;
  step(3);log(clips.length+" scene segment(s) detected; extracting actual thumbnails and waveform");drawTimeline();
  try{const result=await request("/api/visuals",{id:job.id});visuals=new Map(result.visuals.map(v=>[v.id,v]));log("Scene thumbnails and source audio peaks ready");}
  catch(e){log("Visual extraction failed; cuts remain usable: "+e.message,true);}
  step(3,true);drawTimeline();connect(3,$("clip-0"));
}));
$("render").addEventListener("click",()=>action(async()=>{
  step(4);hideExports();log("Rendering "+selected.size+" selected scenes…");
  $("render-progress").value=0;$("render-status").textContent="Submitting";
  try{
    const submitted=await request("/api/render",{id:job.id,clips:[...selected],order:selectedOrder(),edits,...clipperSettings()});
    activeRender=submitted.render_id;updateButtons();
    while(true){
      const state=await request("/api/render/status",{render_id:activeRender});
      $("render-progress").value=state.progress;$("render-status").textContent=state.status+" · "+state.progress+"%";
      if(state.status==="completed"){
        const result=state.result;step(4,true);log("MP4 export complete");$("download").href=result.url;$("download").hidden=false;
        if(result.captions_url){$("download-srt").href=result.captions_url;$("download-srt").hidden=false;}
        connect(4,$("download"));break;
      }
      if(state.status==="failed"||state.status==="cancelled"){log("Render "+state.status,state.status==="failed");break;}
      await new Promise(resolve=>setTimeout(resolve,600));
    }
  }finally{activeRender=null;updateButtons();}

}));
$("video").addEventListener("timeupdate",()=>{$("time").textContent=format($("video").currentTime);updatePlayhead();updateCaptionOverlay();updateEffectPreview();});
$("video").addEventListener("seeked",updateEffectPreview);
$("video").addEventListener("loadedmetadata",()=>{updateEffectPreview();updateButtons();});
$("preview-effects").addEventListener("change",updateEffectPreview);
$("undo").addEventListener("click",()=>restore(history,future));
$("redo").addEventListener("click",()=>restore(future,history));
$("ticks").addEventListener("click",e=>{if(!job)return;stopSequence();const b=$("ticks").getBoundingClientRect();$("video").currentTime=Math.max(0,Math.min(job.duration,(e.clientX-b.left)/b.width*job.duration));updatePlayhead();});
window.addEventListener("resize",updatePlayhead);
$("tracks").addEventListener("scroll",updatePlayhead);
$("file").disabled=true;drawTimeline();
refreshAccount(true);

function refreshCaption(){$("caption-text").value=cues[activeCue]?.text||"";}
function updateCaptionOverlay(){
  const now=$("video").currentTime;
  const active=cues.filter(c=>c.start<=now&&now<c.end), overlay=$("caption-overlay"), mode=$("caption-mode").value;
  overlay.className="caption-"+mode;overlay.replaceChildren();
  if(mode==="karaoke"){
    for(const cue of active){
      const row=document.createElement("div"),words=cue.text.trim().split(/\s+/);
      const progress=Math.min(words.length,Math.floor((now-cue.start)/(cue.end-cue.start)*words.length)+1);
      words.forEach((word,i)=>{const span=document.createElement("span");span.textContent=word+(i<words.length-1?" ":"");if(i<progress)span.className="spoken";row.append(span);});overlay.append(row);
    }
  }else{overlay.textContent=active.map(c=>c.text).join("\n");}
  overlay.hidden=!active.length;
}
function installCues(next){remember();cues=next;activeCue=-1;refreshCaption();hideExports();drawTimeline();log(cues.length+" source-time captions loaded");}
$("srt-file").addEventListener("change",()=>{const file=$("srt-file").files[0];$("srt-file").value="";if(!file)return;action(async()=>{if(file.size>200000)throw new Error("SRT too large");const result=await request("/api/captions/import",{id:job.id,srt:await file.text()});installCues(result.cues);});});
$("transcribe").addEventListener("click",()=>action(async()=>{log("Running local speech recognition…");const result=await request("/api/transcribe",{id:job.id});installCues(result.cues);}));
$("clear-captions").addEventListener("click",()=>{if(!busy)installCues([]);});
$("apply-caption").addEventListener("click",()=>{if(busy||activeCue<0)return;const text=$("caption-text").value.trim();if(!text){log("Caption text cannot be empty",true);return;}remember();cues[activeCue]={...cues[activeCue],text};hideExports();drawTimeline();log("Caption text updated");});

$("music-file").addEventListener("change",()=>{const file=$("music-file").files[0];$("music-file").value="";if(!file)return;action(async()=>{
  if(file.size>64*1024*1024)throw new Error("Maximum music upload is 64 MB");
  log("Decoding music and detecting audio onsets…");
  const result=await request("/api/music/import/"+job.id,file,true);musicData=result;musicName=file.name;$("use-music").checked=true;await loadMonitorMusic();hideExports();drawTimeline();log(result.beats.length+" music onsets detected");
});});
$("use-music").addEventListener("change",()=>{hideExports();drawTimeline();});
for(const id of ["music-gain","source-gain"])$(id).addEventListener("input",()=>{if(sequence){$("download").hidden=true;$("download-srt").hidden=true;syncMonitor();}else hideExports();});
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
    clearDirector();clearClipper();clips=result.clips;selected=new Set(clips.map(c=>c.id));sceneOrder=[];visuals.clear();history=[];future=[];edits={};current=-1;drawTimeline();
    try{const result=await request("/api/visuals",{id:job.id});visuals=new Map(result.visuals.map(v=>[v.id,v]));}catch(e){log("Visual extraction failed: "+e.message,true);}
    drawTimeline();log(clips.length+" beat-based segments created");connect(3,$("clip-0"));
  });
});

$("cinematic").addEventListener("click",()=>{
  if(busy||!selected.size)return;
  remember();
  const palette=["zoom","warm","fade","contrast"];
  let index=0;
  for(const c of clips){
    if(!selected.has(c.id))continue;
    const existing=edited(c);
    const effect=c.end-c.start<.5?"contrast":palette[index%palette.length];
    edits[c.id]={start:existing.start,end:existing.end,effect};index++;
  }
  hideExports();refreshInspector();drawTimeline();log("Cinematic preset applied to "+index+" selected scenes (approximate monitor preview available)");connect(3,$("clip-"+[...selected][0]));
});

$("caption-mode").addEventListener("change",()=>{hideExports();updateCaptionOverlay();log("Caption export style: "+$("caption-mode").value);});

for(const id of ["director-prompt","director-target","director-style","director-provider"])$(id).addEventListener("input",()=>{clearDirector();updateButtons();});
$("director-plan").addEventListener("click",()=>action(async()=>{
  clearDirector();
  const provider=$("director-provider").value, style=$("director-style").value;
  const prompt=$("director-prompt").value.trim()||(provider==="preset"?"Apply "+style+" preset":"");
  if(!prompt)throw new Error("Describe the requested edit");
  log("Generating "+provider+" edit plan…");
  const result=await request("/api/director",{id:job.id,provider,style,prompt,target:$("director-target").valueAsNumber,cues,use_music:$("use-music").checked});
  directorPlan=result;$("director-result").textContent=result.clips.length+" scenes · "+result.duration+"s · "+result.reason;
  log("Validated plan ready for review");updateButtons();
}));
$("director-apply").addEventListener("click",()=>{
  if(busy||!directorPlan)return;
  if(!window.confirm("Apply director selection, trims and effects? Undo is available."))return;
  remember();selected=new Set(directorPlan.clips);sceneOrder=[];edits=directorPlan.edits;current=-1;hideExports();
  const first=directorPlan.clips[0];clearDirector();drawTimeline();log("Director plan applied to timeline");connect(3,$("clip-"+first));
});

$("clipper-suggest").addEventListener("click",()=>action(async()=>{
  log("Ranking candidate source windows…");
  const result=await request("/api/clipper/suggest",{id:job.id,target:Number($("clipper-target").value),count:$("clipper-count").valueAsNumber,style:$("clipper-style").value,cues,use_music:$("use-music").checked});
  clipBatch=result.batch;clipCandidates=result.candidates;clipDownloads.clear();drawClipper();
  $("clipper-status").textContent=clipCandidates.length+" distinct suggestions (heuristic ranking).";
  log(clipCandidates.length+" promotional clip suggestions ready");
}));
$("clipper-render-all").addEventListener("click",()=>action(async()=>{
  if(!clipBatch)return;
  let failures=0;
  for(const c of clipCandidates){
    try{await renderClip(c);}catch(e){failures++;log("Clip "+(c.id+1)+" failed: "+e.message,true);}
  }
  $("clipper-status").textContent=(clipCandidates.length-failures)+" / "+clipCandidates.length+" clips rendered in this batch";
}));

for(const id of ["export-preset","export-framing","export-quality"])$(id).addEventListener("change",()=>{hideExports();updateButtons();log("Export format updated; monitor does not preview output framing");});

async function refreshProjects(){
  const data=await request("/api/projects/list",{});
  projectCount=data.projects.length;
  const select=$("saved-projects"), prior=select.value;
  select.replaceChildren(new Option("Saved projects",""));
  for(const p of data.projects){const opt=new Option(p.name+(p.saved?" · "+format(p.duration):" (delete only)"),p.id);opt.dataset.saved=String(p.saved);select.add(opt);}
  if([...select.options].some(o=>o.value===prior))select.value=prior;
  $("storage-mode").textContent=data.persistent?"Persistent storage":"Session only — restart clears files";
  updateButtons();
}
$("saved-projects").addEventListener("change",updateButtons);
$("save-project").addEventListener("click",()=>action(async()=>{
  const result=await request("/api/projects/save",{id:job.id,name:$("project-name").value,source_mime:sourceMime,studio_brief:studioBrief,selected:[...selected],order:selectedOrder(),edits,...clipperSettings()});
  $("project").textContent=result.name;await refreshProjects();$("saved-projects").value=job.id;log("Saved project: "+result.name);
}));
$("open-project").addEventListener("click",()=>{
  if(busy||!$("saved-projects").value||$("saved-projects").selectedOptions[0]?.dataset.saved!=="true")return;
  if(job&&!window.confirm("Open saved project? Unsaved changes in the current editor will be discarded."))return;
  action(async()=>{
    const result=await request("/api/projects/open",{id:$("saved-projects").value});
    const response=await fetch(result.source_url);if(!response.ok)throw new Error("Saved source unavailable");
    const raw=await response.blob();
    sourceMime=result.state.source_mime;
    if(objectURL)URL.revokeObjectURL(objectURL);
    objectURL=URL.createObjectURL(new Blob([raw],{type:sourceMime}));
    showSequencePosition(0,0);job=result;clearDirector();clearClipper();resetMusic();clips=result.clips;visuals.clear();history=[];future=[];current=-1;activeCue=-1;
    const s=result.state;setStudioBrief(s.studio_brief||null);$("director-prompt").value=(result.director_prompt||"").slice(0,1500);selected=new Set(s.selected);sceneOrder=s.order||[];edits=s.edits;cues=s.cues;musicData=result.music;musicName="Saved soundtrack";await loadMonitorMusic();
    $("use-music").checked=s.use_music;$("music-gain").value=s.music_gain;$("source-gain").value=s.source_gain;$("caption-mode").value=s.caption_mode;$("export-preset").value=s.preset;$("export-framing").value=s.framing;$("export-quality").value=s.quality||"standard";
    $("project-name").value=s.name;$("project").textContent=s.name;$("video").src=objectURL;$("placeholder").hidden=true;$("format").textContent=job.width+" × "+job.height;
    refreshCaption();hideExports();drawTimeline();
    if(clips.length){try{const v=await request("/api/visuals",{id:job.id});visuals=new Map(v.visuals.map(x=>[x.id,x]));}catch(e){log("Visual extraction failed: "+e.message,true);}}
    drawTimeline();log("Opened saved project: "+s.name);
  });
});
$("delete-project").addEventListener("click",()=>{
  const id=$("saved-projects").value||job?.id;if(busy||!id)return;
  const name=$("saved-projects").value?$("saved-projects").selectedOptions[0].textContent:$("project-name").value||"Current import";
  if(!window.confirm("Permanently delete "+name+" and all its media and exports?"))return;
  action(async()=>{
    await request("/api/projects/delete",{id});
    if(job?.id===id){
      if(objectURL)URL.revokeObjectURL(objectURL);objectURL=null;$("video").removeAttribute("src");$("video").load();
      job=null;sceneOrder=[];setStudioBrief(null);clearDirector();clearClipper();resetMusic();clips=[];selected.clear();sceneOrder=[];edits={};cues=[];visuals.clear();history=[];future=[];current=-1;activeCue=-1;refreshCaption();hideExports();
      $("placeholder").hidden=false;$("project").textContent="Untitled sequence";$("project-name").value="";$("format").textContent="NO MEDIA";
    }
    await refreshProjects();log("Project deleted");
  });
});

$("cancel-render").addEventListener("click",async()=>{if(!activeRender)return;try{const state=await request("/api/render/cancel",{render_id:activeRender});$("render-status").textContent=state.status;log("Render cancellation requested");}catch(e){log(e.message,true);}});

async function refreshUsage(){
  if(accountInvalid||!account)return;
  try{
    const response=await fetch("/api/usage",{cache:"no-store"});if(!response.ok)throw new Error("Usage unavailable");
    const data=await response.json();if(accountInvalid)return;
    usageState=PlanUI.usage(data);
    $("usage-summary").textContent=usageState?data.month+" · "+usageState.label:"Usage unavailable";
    $("usage-meter").hidden=!usageState||usageState.ratio===null;
    if(!$("usage-meter").hidden)$("usage-meter").value=100*usageState.ratio;
  }catch(e){usageState=null;$("usage-summary").textContent="Usage unavailable";$("usage-meter").hidden=true;}
  updateButtons();
}

function applyAccountControls(){
  const p=account?.capabilities;
  $("refresh-account").disabled=busy||accountRefreshing;
  if(!account||accountInvalid||accountRefreshing){
    for(const id of ["file","analyze","render","studio-pack","save-project","open-project","delete-project","transcribe","music-file","use-music","detect-beats","beat-cut","director-plan","director-apply"])$(id).disabled=true;
    return;
  }
  for(const option of $("export-preset").options)option.disabled=!PlanUI.preset(p,option.value,job);
  for(const option of $("export-quality").options)option.disabled=!PlanUI.quality(p,option.value);
  for(const option of $("caption-mode").options)option.disabled=option.value!=="soft"&&!canFeature("animated_captions");
  $("director-provider").querySelector('option[value="ollama"]').disabled=!canFeature("ollama");
  $("director-plan").disabled ||= $("director-provider").value==="ollama"&&!canFeature("ollama");
  $("director-apply").disabled ||= $("director-provider").value==="ollama"&&!canFeature("ollama");
  $("studio-pack").disabled ||= !canFeature("studio_pack");
  $("transcribe").disabled ||= !canFeature("transcribe");
  for(const id of ["music-file","detect-beats","beat-cut","beat-interval","music-gain"])$(id).disabled ||= !canFeature("music");
  // A downgraded user can still uncheck a saved soundtrack to make a permitted export.
  $("use-music").disabled=busy||(!musicData&&!$("use-music").checked)||(!canFeature("music")&&!$("use-music").checked);
  if(p&&projectCount!==null&&projectCount>=p.max_projects)$("file").disabled=true;
  const seconds=clips.filter(c=>selected.has(c.id)).reduce((a,c)=>a+edited(c).end-edited(c).start,0);
  const allowed=PlanUI.render(p,clipperSettings(),job,seconds);
  const quotaExceeded=usageState?.remaining!=null&&Math.ceil(seconds)>usageState.remaining;
  $("render").disabled ||= !allowed||quotaExceeded;
  $("account-message").textContent=quotaExceeded&&selected.size?"Selected export exceeds the remaining monthly render quota.":!allowed&&selected.size?"Selected export settings exceed this workspace’s capabilities. Choose permitted settings.":p&&projectCount!==null&&projectCount>=p.max_projects?"Project limit reached. Delete an unused project before importing.":"";
}
async function refreshAccount(initial=false){
  if(accountRefreshing||busy)return;
  if(accountInvalid){window.location.reload();return;}
  accountRefreshing=true;updateButtons();
  try{
    const response=await fetch("/api/session",{cache:"no-store"});if(!response.ok)throw new Error("Session unavailable");
    const data=await response.json();if(typeof data.token!=="string"||!data.token)throw new Error("Session unavailable");
    if(account&&(account.workspace!==data.workspace||token!==data.token)){
      // Never retain another workspace's media in a newly authenticated editor.
      accountInvalid=true;token=null;window.location.reload();return;
    }
    account=data;token=data.token;
    if(!canFeature("music"))clearMonitorMusic();
    $("account-plan").textContent=data.plan?"C4PCUT "+data.plan.toUpperCase():data.workspace?"Private workspace":"Local editor";
    const p=data.capabilities;
    $("account-policy").textContent=p?"Max edge "+p.max_output_edge+" px · "+p.max_render_seconds+" s/export · "+p.max_projects+" projects · "+(p.qualities.join(", ")||"no export quality"):"No additional workspace capability restrictions";
    if(initial)log(data.workspace?"Private workspace: "+data.workspace:"Local processing engine ready");
    await refreshProjects();
    await refreshUsage();
  }catch(e){
    $("account-plan").textContent="Connection unavailable";$("account-policy").textContent="Refresh account to reconnect";
    $("usage-summary").textContent="Usage unavailable";$("usage-meter").hidden=true;
    accountInvalid=true;token=null;log("Account authorization unavailable",true);
  }finally{accountRefreshing=false;updateButtons();}
}
$("refresh-account").addEventListener("click",()=>refreshAccount());
document.addEventListener("visibilitychange",()=>{if(!document.hidden&&!busy&&account)refreshAccount();});
setInterval(()=>{if(!document.hidden&&!busy&&account&&!accountInvalid)refreshAccount();},30000);

function setStudioBrief(brief){
  studioBrief=brief;
  $("studio-brief-label").textContent=brief?"Attached: "+brief.title+" · "+brief.language.toUpperCase():"No Studio brief attached";
  if(!brief)$("director-prompt").value="";
}
$("studio-pack").addEventListener("change",()=>{
  const file=$("studio-pack").files[0];$("studio-pack").value="";
  if(!file||!job||busy)return;
  if(!window.confirm("Attach creative brief to current project? This replaces the project name and Director prompt, without starting generation."))return;
  action(async()=>{
    if(file.size>16384)throw new Error("Studio pack too large");
    const result=await request("/api/studio/import-pack",JSON.parse(await file.text()));
    setStudioBrief(result.brief);clearDirector();$("project-name").value=result.brief.title;$("project").textContent=result.brief.title;
    $("director-prompt").value=result.director_prompt.slice(0,1500);
    log("Studio creative brief imported; no generation or billing triggered");
  });
});
$("clear-studio-brief").addEventListener("click",()=>{if(busy||!studioBrief)return;if(!window.confirm("Detach brief and clear Director prompt?"))return;setStudioBrief(null);clearDirector();updateButtons();});
