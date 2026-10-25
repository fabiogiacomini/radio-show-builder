"use strict";
const $ = (id) => document.getElementById(id);
const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (c) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
let project = null, config = null, currentStep = "idea", dirty = false, busy = false;
let jobsTimer = null;
document.querySelector("main").appendChild($("job"));
const newId = () => crypto.randomUUID().replaceAll("-", "");
function notify(message, error = false) {
  $("notice").textContent = message;
  $("notice").classList.toggle("error", error);
  $("notice").hidden = !message;
}
async function api(path, options = {}) {
  const response = await fetch(path, {credentials:"same-origin", ...options});
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "The request failed.");
  return data;
}
function jsonRequest(method, body) { return {method, headers:{"Content-Type":"application/json"}, body:JSON.stringify(body)}; }
function projectURL(suffix = "") { return "/api/projects/" + project.id + suffix; }
function markDirty() { if (project && !busy) { dirty = true; $("save").textContent = "Save changes •"; } }
function seconds(value) {
  const n = Math.round(Number(value) || 0);
  return String(Math.floor(n/3600)).padStart(2,"0")+":"+String(Math.floor(n/60)%60).padStart(2,"0")+":"+String(n%60).padStart(2,"0");
}
function newEntry(kind) { return {id:newId(),kind,title:kind==="speech"?"Spoken segment":"Artist — Track",text:"",notes:"",estimated_seconds:kind==="speech"?60:240,asset_id:null,trim_start:0,trim_end:null}; }
async function projectsList() {
  const result = await api("/api/projects");
  $("project-list").innerHTML = result.projects.map((p) => '<button class="project-item '+(project?.id===p.id?"selected":"")+'" data-project="'+esc(p.id)+'">'+esc(p.title)+'</button>').join("");
}
function assetOptions(selected, empty = "Choose an uploaded file") {
  return '<option value="">'+esc(empty)+'</option>'+Object.values(project.assets).map((a)=>'<option value="'+a.id+'" '+(a.id===selected?"selected":"")+'>'+esc(a.name)+'</option>').join("");
}
function showStep(step) {
  currentStep = step;
  document.querySelectorAll(".step").forEach((e)=>e.hidden=e.id!=="step-"+step);
  document.querySelectorAll(".tabs button").forEach((b)=>b.classList.toggle("active",b.dataset.step===step));
  if(step==="export" && project) refreshTiming().catch(error=>notify(error.message,true));
}
function fillProject() {
  $("welcome").hidden = true; $("editor").hidden = false;
  $("show-name").textContent = project.title;
  for (const [id,key] of [["title","title"],["idea","idea"],["language","language"],["tone","tone"],["research-notes","research_notes"],["verification-notes","verification_notes"]]) $(id).value=project[key]||"";
  const s=project.settings;
  const settingsFields={"duration-mode":"duration_mode","bitrate":"bitrate_kbps","sample-rate":"sample_rate","crossfade":"crossfade_seconds","intro":"intro_seconds","outro":"outro_seconds","bed":"bed_db","music-lufs":"music_lufs","speech-lufs":"speech_lufs","true-peak":"true_peak_db"};
  for(const [id,key] of Object.entries(settingsFields)) $(id).value=s[key];
  $("duration").value=s.target_seconds/60;
  $("music-percent").value=project.music_percent??83;
  $("bed-value").textContent=s.bed_db+" dB";
  $("checks-section").hidden=!project.verification_notes;
  $("jingle-select").innerHTML=assetOptions(project.jingle_id,"No jingle");
  renderSegments(); delivery();
  dirty=false; $("save").textContent="Save changes";
}
function capture() {
  if (!project) return;
  for(const [id,key] of [["title","title"],["idea","idea"],["language","language"],["tone","tone"],["research-notes","research_notes"],["verification-notes","verification_notes"]]) project[key]=$(id).value;
  const fields={"bitrate":"bitrate_kbps","sample-rate":"sample_rate","crossfade":"crossfade_seconds","intro":"intro_seconds","outro":"outro_seconds","bed":"bed_db","music-lufs":"music_lufs","speech-lufs":"speech_lufs","true-peak":"true_peak_db"};
  for(const [id,key] of Object.entries(fields)) project.settings[key]=Number($(id).value);
  project.settings.target_seconds=Number($("duration").value)*60;
  project.settings.duration_mode=$("duration-mode").value;
  project.music_percent=Number($("music-percent").value);
  project.jingle_id=$("jingle-select").value||null;
  document.querySelectorAll(".segment").forEach((node)=>{
    const e=project.entries.find((e)=>e.id===node.dataset.id);
    if(!e)return;
    node.querySelectorAll("[data-field]").forEach((input)=>{
      let value=input.value;
      if(input.dataset.field==="estimated_seconds"||input.dataset.field==="trim_start") value=Number(value);
      if(input.dataset.field==="trim_end") value=value===""?null:Number(value);
      if(input.dataset.field==="asset_id") value=value||null;
      e[input.dataset.field]=value;
    });
  });
}
async function save() {
  if(!project)return;
  if(busy)throw new Error("Wait for the running task to finish.");
  capture();
  project=await api(projectURL(),jsonRequest("PUT",project));
  dirty=false; $("save").textContent="Save changes"; $("show-name").textContent=project.title;
  delivery(); await projectsList();
}
function renderSegments() {
  $("segments").innerHTML=project.entries.map((e,i)=>{
    const a=project.assets[e.asset_id];
    return '<article class="segment" data-id="'+e.id+'"><div class="segment-top"><span class="number">'+String(i+1).padStart(2,"0")+'</span><span class="kind '+e.kind+'">'+e.kind.toUpperCase()+'</span><input data-field="title" aria-label="Segment title" value="'+esc(e.title)+'"><div class="controls"><button class="icon-button" data-action="up" aria-label="Move segment up" '+(i===0?"disabled":"")+'>↑</button><button class="icon-button" data-action="down" aria-label="Move segment down" '+(i===project.entries.length-1?"disabled":"")+'>↓</button><button class="icon-button" data-action="remove" aria-label="Remove segment">×</button></div></div>'+
    (e.kind==="speech"?'<textarea data-field="text" aria-label="Spoken script" rows="5" placeholder="Write the full spoken script…">'+esc(e.text)+'</textarea>':'<p class="help">'+esc(e.notes||"Upload the exact track version you want to include.")+'</p>')+
    '<div class="audio-row"><label class="button light small file-label">'+(a?"Replace audio":"Upload audio")+'<input type="file" data-upload="'+e.id+'" accept="audio/*" hidden></label><select data-field="asset_id" aria-label="Assigned audio file">'+assetOptions(e.asset_id)+'</select><span>'+(a?seconds(a.duration_seconds):"No audio yet")+'</span>'+(a?'<audio controls preload="none" src="'+projectURL("/assets/"+a.id)+'"></audio>':"")+'</div>'+
    '<details><summary>Notes, duration and trim points</summary><label>Production notes<textarea data-field="notes" rows="2">'+esc(e.notes)+'</textarea></label><div class="grid three"><label>Estimate · seconds<input data-field="estimated_seconds" type="number" min=".01" step="any" value="'+e.estimated_seconds+'"></label><label>Start at · seconds<input data-field="trim_start" type="number" min="0" step=".01" value="'+e.trim_start+'"></label><label>End at · seconds<input data-field="trim_end" type="number" min="0" step=".01" value="'+(e.trim_end??"")+'" placeholder="End of file"></label></div><p class="help">Trim points apply only to this segment. The original upload is kept intact.</p></details></article>';
  }).join("");
  $("word-download").href=projectURL("/script.docx");
  $("json-download").href=projectURL("/project.json");
}
function providerConfig() {
  return {provider:$("provider").value,base_url:$("base-url").value,protocol:$("protocol").value,
          api_key:$("api-key").value,model:$("model").value,max_tokens:Number($("max-tokens").value),timeout_seconds:Number($("request-timeout").value)};
}
function selectProvider() {
  const p=config.providers.find(p=>p.id===$("provider").value);
  $("base-url").value=p.base_url; $("protocol").value=p.protocol;
  $("api-key").value=""; $("api-key").placeholder=p.local?"Not required for most local servers":"Only sent to the selected service";
  $("model").value=""; $("model-list").innerHTML="";
  $("request-timeout").value=p.local?1800:300;
}
function lockUI(value) {
  busy=value;
  $("editor").inert=value;
  for(const id of ["new-project","new-preset","start-project","start-radio"]) $(id).disabled=value;
  document.querySelectorAll(".project-item").forEach(b=>b.disabled=value);
  // The job status stays readable even while the editor is inert.
}
async function watchJob(id, type) {
  $("job").hidden=false; lockUI(true);
  async function poll() {
    try {
      const j=await api("/api/jobs/"+id);
      $("job-message").textContent=j.message;
      $("job-progress").value=j.progress;
      if(j.status==="running"){jobsTimer=setTimeout(poll,1000);return;}
      lockUI(false); $("job").hidden=true;
      if(j.status==="error") {notify(j.message,true);return;}
      project=await api(projectURL()); fillProject(); await projectsList();
      showStep(type==="generate"?"rundown":"export");
      notify(type==="generate"?"Draft ready. Review the facts and wording before recording.":"Your MP3 passed the export checks.");
    }catch(error){lockUI(false);$("job").hidden=true;notify(error.message,true);}
  }
  await poll();
}
function delivery() {
  const exp=project.export;
  $("delivery").hidden=!exp;
  if(!exp){$("final-audio").removeAttribute("src");return;}
  $("export-details").textContent=seconds(exp.duration_seconds)+" · "+exp.bitrate_kbps+" kbps CBR · "+exp.integrated_lufs+" LUFS · peak "+exp.true_peak_db+" dBTP";
  const base=projectURL("/exports/");
  $("final-audio").src=base+"show.mp3?preview=1";
  $("mp3-download").href=base+"show.mp3"; $("rundown-download").href=base+"rundown.txt"; $("report-download").href=base+"report.json";
}
async function upload(file, entryId=null) {
  if(!file)return;
  await save();
  notify("Uploading "+file.name+"…");
  const asset=await api(projectURL("/assets?filename="+encodeURIComponent(file.name)),{method:"POST",body:file,headers:{"Content-Type":"application/octet-stream"}});
  project.assets[asset.id]=asset;
  if(entryId) project.entries.find(e=>e.id===entryId).asset_id=asset.id;
  else project.jingle_id=asset.id;
  // Update the existing controls before saving so capture does not restore the previous assignment.
  if(entryId) {
    const select=document.querySelector('[data-id="'+entryId+'"] [data-field="asset_id"]');
    if(select){select.innerHTML=assetOptions(asset.id);select.value=asset.id;}
  }else{
    $("jingle-select").innerHTML=assetOptions(asset.id,"No jingle");$("jingle-select").value=asset.id;
  }
  await save(); fillProject(); showStep("rundown"); notify("Audio uploaded. Original files are kept unchanged.");
}
async function timing() {
  await save();
  return refreshTiming();
}
async function refreshTiming() {
  const result=await api(projectURL("/analyse"));
  const difference=result.difference_seconds;
  $("timing").innerHTML='<strong>'+seconds(result.base_seconds)+'</strong><span>'+(result.missing.length?"Planning estimate · "+result.missing.length+" segment(s) still need audio.":project.settings.duration_mode==="natural"?"Natural duration · determined by your recordings and selected transitions.":Math.abs(difference).toFixed(1)+" seconds "+(difference>0?"over":"under")+" the target before any extra closing jingle.")+'</span>'+(difference>0&&project.settings.duration_mode==="exact"?'<p class="problem">Remove a segment or set trim points before building.</p>':"");
  return result;
}
function safe(action) {return async(event)=>{try{await action(event);}catch(error){notify(error.message,true);}};}
async function createProject(preset) {
  if(dirty&&!confirm("Discard unsaved changes and create a new project?"))return;
  project=await api("/api/projects",jsonRequest("POST",{preset}));
  fillProject();showStep("idea");await projectsList();notify("");
}
$("new-project").onclick=safe(()=>createProject($("new-preset").value));
$("start-project").onclick=safe(()=>createProject("podcast"));
$("start-radio").onclick=safe(()=>createProject("radio"));
$("new-preset").onchange=()=>{$("new-project").textContent=$("new-preset").value==="podcast"?"＋ New podcast":"＋ New radio show";};
$("project-list").onclick=safe(async(event)=>{
  const b=event.target.closest("[data-project]");if(!b||busy)return;
  if(dirty&&!confirm("Discard unsaved changes and open this project?"))return;
  project=await api("/api/projects/"+b.dataset.project);
  fillProject();showStep("idea");await projectsList();notify("");
});
$("save").onclick=safe(async()=>{await save();notify("Project saved on your computer.");});
document.querySelectorAll("[data-step]").forEach(b=>b.onclick=safe(async()=>{if(dirty)await save();showStep(b.dataset.step);}));
$("editor").addEventListener("input",event=>{if(!event.target.closest("#api-key,#provider,#model,#base-url,#protocol,#max-tokens,#request-timeout"))markDirty();});
$("bed").oninput=()=>{$("bed-value").textContent=$("bed").value+" dB";};
$("provider").onchange=selectProvider;
$("load-models").onclick=safe(async()=>{
  $("load-models").disabled=true;
  try{const result=await api("/api/models",jsonRequest("POST",providerConfig()));$("model-list").innerHTML=result.models.map(m=>'<option value="'+esc(m)+'">').join("");notify(result.models.length+" model IDs loaded. Choose a text-generation model.");}
  finally{$("load-models").disabled=false;}
});
$("generate").onclick=safe(async()=>{
  await save(); if(!project.idea.trim())throw new Error("Describe your episode or show idea first.");
  if(project.entries.length&&!confirm("Replace this rundown with a new draft? Your uploaded files will remain available."))return;
  const result=await api(projectURL("/generate"),jsonRequest("POST",{provider:providerConfig(),music_percent:Number($("music-percent").value),replace_existing:true}));
  await watchJob(result.job_id,"generate");
});
$("blank").onclick=safe(async()=>{
  capture();
  if(project.entries.length){showStep("rundown");return;}
  project.entries=project.preset==="podcast"
    ? ["Opening","Main story","Closing"].map(title=>({...newEntry("speech"),title}))
    : [newEntry("speech"),newEntry("music"),newEntry("speech")];
  renderSegments();await save();showStep("rundown");
});
$("import-json").onchange=safe(async(event)=>{
  const file=event.target.files[0];if(!file)return;
  if(file.size>2000000)throw new Error("This rundown file is too large.");
  const imported=JSON.parse(await file.text());
  if(!Array.isArray(imported.entries))throw new Error("Choose a Radio Show Builder rundown JSON file.");
  if(project.entries.length&&!confirm("Replace the current rundown with the imported one?"))return;
  imported.entries=imported.entries.map(e=>({...e,id:newId(),asset_id:null}));
  imported.jingle_id=null;
  project=await api(projectURL(),jsonRequest("PUT",imported));
  fillProject();showStep("rundown");notify("Rundown imported. Upload your audio to continue.");
});
$("segments").onclick=safe(async(event)=>{
  const b=event.target.closest("[data-action]");if(!b)return;capture();
  const index=project.entries.findIndex(e=>e.id===b.closest(".segment").dataset.id);
  if(b.dataset.action==="remove"){
    if(!confirm("Remove this segment from the rundown? Its audio file will remain available."))return;
    project.entries.splice(index,1);
  }else{
    const next=index+(b.dataset.action==="up"?-1:1);
    [project.entries[index],project.entries[next]]=[project.entries[next],project.entries[index]];
  }
  renderSegments();markDirty();
});
$("segments").onchange=safe(async(event)=>{
  if(event.target.dataset.upload)await upload(event.target.files[0],event.target.dataset.upload);
  else if(event.target.dataset.field==="asset_id"){capture();renderSegments();markDirty();}
});
$("jingle-upload").onchange=safe(event=>upload(event.target.files[0]));
$("jingle-select").onchange=markDirty;
for(const kind of ["speech","music"]) $("add-"+kind).onclick=()=>{capture();project.entries.push(newEntry(kind));renderSegments();markDirty();};
$("go-export").onclick=safe(async()=>{await save();showStep("export");await timing();});
$("check-timing").onclick=safe(timing);
$("render").onclick=safe(async()=>{
  await save();
  if(!config.ffmpeg_available)throw new Error("Install FFmpeg and restart Radio Show Builder before building the MP3.");
  const result=await api(projectURL("/render"),jsonRequest("POST",{}));await watchJob(result.job_id,"render");
});
for(const id of ["word-download","json-download"]) $(id).onclick=safe(async(event)=>{
  event.preventDefault();await save();const link=document.createElement("a");link.href=$(id).href;
  if(id==="json-download")link.download="radio-show-project.json";link.click();
});
window.addEventListener("beforeunload",event=>{if(dirty){event.preventDefault();event.returnValue="";}});
$("quit-app").onclick=safe(async()=>{
  if(busy)throw new Error("Wait for the running task to finish before quitting.");
  if(dirty)await save();
  await api("/api/shutdown",{method:"POST"});
  $("quit-app").disabled=true;
  $("editor").inert=true;
  $("new-project").disabled=true;
  $("start-project").disabled=true;
  $("start-radio").disabled=true;
  $("new-preset").disabled=true;
  notify("Radio Show Builder has stopped. You can close this tab. Reopen the app to continue.");
});
(async()=>{
  try{
    const token=new URLSearchParams(location.hash.slice(1)).get("token");
    const opts={method:"POST",headers:token?{"X-Session-Token":token}:{}};
    await api("/api/session",opts);
    history.replaceState(null,"",location.pathname);
    config=await api("/api/config");
    $("version").textContent="v"+config.version;
    $("quit-app").hidden=false;
    $("provider").innerHTML=config.providers.map(p=>'<option value="'+p.id+'">'+esc(p.name)+'</option>').join("");
    selectProvider();await projectsList();
    if(!config.ffmpeg_available)notify("FFmpeg is not installed. You can write scripts now; install FFmpeg before mixing audio.",true);
  }catch(error){notify(error.message,true);}
})();
