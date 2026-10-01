const TOKEN=(()=>{try{return localStorage.getItem("aarogyam_token")||""}catch(e){return""}})();
let settings={};
let templateUrl="";
let templateObjectUrl="";

async function showAuthenticatedTemplate(){
  try{
    const r=await fetch("/api/settings/template/preview?t="+Date.now(),{
      headers:auth(),
      cache:"no-store"
    });

    if(!r.ok){
      throw new Error(await r.text() || "Could not load template preview");
    }

    const blob=await r.blob();

    if(templateObjectUrl){
      URL.revokeObjectURL(templateObjectUrl);
    }

    templateObjectUrl=URL.createObjectURL(blob);
    $("templateBg").src=templateObjectUrl;
    $("templateBg").style.display="block";
    $("templateName").textContent="Uploaded letterhead";
    return true;
  }catch(e){
    console.error("Template preview error:",e);
    $("templateBg").removeAttribute("src");
    $("templateBg").style.display="none";
    $("templateName").textContent="Template preview unavailable";
    return false;
  }
}
const $=id=>document.getElementById(id);
const auth=()=>TOKEN?{Authorization:"Bearer "+TOKEN}:{};

const defaults={
 page:{size:"A4",left:52,right:52,top:132,bottom:82,auto_break:true,repeat_table_header:true},
 patient:{
  visible:["name","age","sex","code","uhid","referred_by","received_on","reported_on","phone"],
  columns:2,style:"card",font_size:8.5,spacing:12,label_bold:true,position:{x:0,y:0}
 },
 results:{
  columns:["name","value","unit","reference_range"],
  font_size:9,header_size:7.5,section_font_size:8,
  section_bold:true,show_grid:false,section_background:"#ECEAFB",
  row_spacing:5
 },
 appearance:{text:"#151A2D",accent:"#5F52E8",font:"Helvetica"},
 manual:{header_text:"",footer_text:"",text_color:"#52606D",logo_path:""}
};

const merge=a=>({
 ...defaults,...a,
 page:{...defaults.page,...(a?.page||{})},
 patient:{...defaults.patient,...(a?.patient||{})},
 results:{...defaults.results,...(a?.results||{})},
 appearance:{...defaults.appearance,...(a?.appearance||{})},
 manual:{...defaults.manual,...(a?.manual||{})}
});

const show=(m,hold=false)=>{
 const e=$("status");
 e.textContent=m;e.style.display="block";
 if(!hold)setTimeout(()=>e.style.display="none",2200);
};

async function api(url,opts={}){
 opts.headers={...(opts.headers||{}),...auth()};
 const r=await fetch(url,opts);
 const j=await r.json().catch(()=>({}));
 if(!r.ok)throw Error(j.detail||("Request failed ("+r.status+")"));
 return j;
}

function goBack(){location.href="/";}

function renderPreview(){
 const p=$("pvPatient");
 p.innerHTML="";

 const fields=[
  ["showName","Patient Name","Sample Patient"],
  ["showAge","Age / Gender","32Y / M"],
  ["showCode","Patient ID","PT-001"],
  ["showUhid","UHID","UHID-001"],
  ["showRef","Referred By","Dr. Example"],
  ["showReceived","Received On","01 Oct 2026"],
  ["showReported","Reported On","01 Oct 2026"],
  ["showPhone","Phone","+91 98xxxxxx"]
 ];

 fields.filter(x=>$(x[0]).checked).forEach(x=>{
  const d=document.createElement("div");
  d.className="pv";
  d.innerHTML="<b>"+x[1]+"</b><span>"+x[2]+"</span>";
  p.appendChild(d);
 });

 p.style.gridTemplateColumns=$("patientCols").value==="1"?"1fr":"1fr 1fr";

 $("paper").style.fontFamily=$("font").value;
 $("paper").style.color="#151A2D";

 const patient=$("patientBlock");
 const reportFlow=$("reportFlow");
 const oldPatient=merge(settings.report_layout||{}).patient;
 const pos=oldPatient.position||{x:0,y:0};
 patient.style.marginTop=$("patientSpacing").value+"px";
 const x=Number(pos.x)||0;
 const y=Number(pos.y)||0;
 patient.style.transform=`translate(${x}px, ${y}px)`;
 if(reportFlow) reportFlow.style.transform=`translate(0px, ${y}px)`;
 patient.style.fontSize=$("patientFont").value+"px";

 document.querySelector(".report-title").style.fontSize=
   Math.max(10,Number($("fontSize").value)+3)+"px";

 document.querySelector(".section").style.fontSize=
   Number($("sectionSize").value)+"px";

 document.querySelectorAll(".tr").forEach(x=>{
   x.style.paddingTop=$("rowSpacing").value+"px";
   x.style.paddingBottom=$("rowSpacing").value+"px";
   x.style.border= $("gridStyle").checked
     ?"1px solid #dfe3ec"
     :"";
 });

 document.querySelector(".section").style.fontWeight=
   $("boldSections").checked?"700":"400";
}

function collect(){
 const visible=[];
 const map={
  showName:"name",showAge:"age",showCode:"code",showUhid:"uhid",
  showRef:"referred_by",showReceived:"received_on",
  showReported:"reported_on",showPhone:"phone"
 };

 for(const [id,key] of Object.entries(map))
  if($(id).checked)visible.push(key);

 const old=merge(settings.report_layout||{});

 return {
  ...old,
  page:{
   ...old.page,
   size:$("pageSize").value,
   top:Number($("reportTop").value),
   auto_break:$("autoBreak").value==="true",
   repeat_table_header:$("repeatHeader").value==="true"
  },
  patient:{
   ...old.patient,
   visible,
   columns:Number($("patientCols").value),
   style:$("patientStyle").value,
   font_size:Number($("patientFont").value),
   spacing:Number($("patientSpacing").value),
   position:{
    x:Number(old.patient?.position?.x)||0,
    y:Number(old.patient?.position?.y)||0
   }
  },
  results:{
   ...old.results,
   font_size:Number($("fontSize").value),
   section_font_size:Number($("sectionSize").value),
   row_spacing:Number($("rowSpacing").value),
   show_grid:$("gridStyle").checked,
   columns:[
    "name","value",
    ...($("showUnit").checked?["unit"]:[]),
    ...($("showReference").checked?["reference_range"]:[])
   ]
  },
  appearance:{
   ...old.appearance,
   font:$("font").value
  },
  manual:old.manual
 };
}

function enablePatientDrag(){
 const paper=$("paper");
 const patient=$("patientBlock");
 if(!paper || !patient || patient.dataset.dragReady==="1") return;

 patient.dataset.dragReady="1";
 patient.style.pointerEvents="auto";
 patient.style.touchAction="none";
 patient.style.cursor="grab";
 patient.style.zIndex="10";

 let dragging=false;
 let pointerId=null;
 let startClientX=0;
 let startClientY=0;
 let originX=0;
 let originY=0;
 let pendingX=0;
 let pendingY=0;
 let frame=0;

 const getPosition=()=>{
  const layout=merge(settings.report_layout||{});
  return layout.patient.position||{x:0,y:0};
 };

 const applyPosition=(x,y)=>{
  patient.style.transform=`translate(${x}px, ${y}px)`;
  const reportFlow=$("reportFlow");
  if(reportFlow) reportFlow.style.transform=`translate(0px, ${y}px)`;
 };

 const flush=()=>{
  frame=0;
  if(!dragging) return;
  applyPosition(pendingX,pendingY);
 };

 patient.addEventListener("pointerdown",e=>{
  if(e.button!==undefined && e.button!==0) return;
  e.preventDefault();

  const pos=getPosition();
  const rect=paper.getBoundingClientRect();
  const scaleX=rect.width/paper.offsetWidth||1;
  const scaleY=rect.height/paper.offsetHeight||1;

  dragging=true;
  pointerId=e.pointerId;
  startClientX=e.clientX;
  startClientY=e.clientY;
  originX=Number(pos.x)||0;
  originY=Number(pos.y)||0;

  patient.style.cursor="grabbing";
  patient.style.zIndex="10";
  patient.setPointerCapture?.(e.pointerId);

  patient.dataset.dragScaleX=String(scaleX);
  patient.dataset.dragScaleY=String(scaleY);
 });

 patient.addEventListener("pointermove",e=>{
  if(!dragging || e.pointerId!==pointerId) return;
  e.preventDefault();

  const scaleX=Number(patient.dataset.dragScaleX)||1;
  const scaleY=Number(patient.dataset.dragScaleY)||1;

  pendingX=originX+(e.clientX-startClientX)/scaleX;
  pendingY=originY+(e.clientY-startClientY)/scaleY;

  if(!frame) frame=requestAnimationFrame(flush);
 });

 const finish=e=>{
  if(!dragging || e.pointerId!==pointerId) return;

  if(frame){
   cancelAnimationFrame(frame);
   frame=0;
  }

  const layout=merge(settings.report_layout||{});
  layout.patient.position={
   x:Math.round(pendingX*10)/10,
   y:Math.round(pendingY*10)/10
  };
  settings.report_layout=layout;

  applyPosition(layout.patient.position.x,layout.patient.position.y);

  dragging=false;
  pointerId=null;
  patient.style.cursor="grab";
  try{patient.releasePointerCapture?.(e.pointerId)}catch(_){}
 };

 patient.addEventListener("pointerup",finish);
 patient.addEventListener("pointercancel",finish);
}

async function uploadTemplate(){
 const f=$("templateFile").files[0];
 if(!f)return alert("Choose a PDF or Word letterhead first.");

 const fd=new FormData();
 fd.append("file",f);

 try{
  show("Uploading letterhead…",true);
  await api("/api/settings/template",{method:"POST",body:fd});

  await showAuthenticatedTemplate();
  $("templateName").textContent=f.name;

  show("Letterhead uploaded");
 }catch(e){
  show("Upload failed: "+e.message,true);
 }
}

async function saveDesign(){
 try{
  show("Saving report design…",true);

  const layout=collect();

  const f=new URLSearchParams({
   whatsapp_enabled:String(settings.whatsapp_enabled||false),
   upi_id:String(settings.upi_id||""),
   report_layout:JSON.stringify(layout)
  });

  await api("/api/settings",{method:"PUT",body:f});
  settings.report_layout=layout;

  show("Report design saved");
 }catch(e){
  show("Save failed: "+e.message,true);
 }
}

async function loadTemplate(){
 try{
  const r=await fetch("/api/settings/template",{
   headers:auth(),
   cache:"no-store"
  });

  if(r.ok){
   await showAuthenticatedTemplate();
   $("templateName").textContent="Uploaded letterhead";
  }
 }catch(e){}
}

async function init(){
 try{
  show("Loading report design…",true);

  settings=await api("/api/settings");
  const l=merge(settings.report_layout||{});

  $("pageSize").value=l.page.size||"A4";
  $("patientStyle").value=l.patient.style||"card";
  $("patientCols").value=l.patient.columns||2;
  $("patientFont").value=l.patient.font_size||8.5;
  $("patientSpacing").value=l.patient.spacing??12;
  if($("patientTop")) $("patientTop").value=l.patient.top_spacing??0;

  $("font").value=l.appearance.font||"Helvetica";
  $("fontSize").value=l.results.font_size||9;
  $("sectionSize").value=l.results.section_font_size||8;
  $("rowSpacing").value=l.results.row_spacing??5;

  $("gridStyle").checked=!!l.results.show_grid;
  $("showUnit").checked=(l.results.columns||[]).includes("unit");
  $("showReference").checked=(l.results.columns||[]).includes("reference_range");
  $("boldSections").checked=l.results.section_bold!==false;

  $("autoBreak").value=String(l.page.auto_break!==false);
  $("repeatHeader").value=String(l.page.repeat_table_header!==false);
  $("reportTop").value=l.page.top||132;
  if($("reportTopSpacing")) $("reportTopSpacing").value=l.page.report_top_spacing??0;

  const map={
   showName:"name",showAge:"age",showCode:"code",showUhid:"uhid",
   showRef:"referred_by",showReceived:"received_on",
   showReported:"reported_on",showPhone:"phone"
  };

  for(const [id,key] of Object.entries(map))
   $(id).checked=(l.patient.visible||[]).includes(key);

  [
   "patientStyle","patientCols","patientFont","patientSpacing",
   "font","fontSize","sectionSize","rowSpacing","gridStyle",
   "showUnit","showReference","boldSections",
   "pageSize","autoBreak","repeatHeader","reportTop",
   "showName","showAge","showCode","showUhid","showRef",
   "showReceived","showReported","showPhone"
  ].forEach(id=>$(id).addEventListener("input",renderPreview));

  await loadTemplate();
  renderPreview();
  enablePatientDrag();
  show("Report design ready");

 }catch(e){
  show("Could not load report design: "+e.message,true);
 }
}

init();
