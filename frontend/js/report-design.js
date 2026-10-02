const TOKEN=(()=>{try{return localStorage.getItem("aarogyam_token")||""}catch(e){return""}})();
let settings={};
let templateObjectUrl="";

const $=id=>document.getElementById(id);
const auth=()=>TOKEN?{Authorization:"Bearer "+TOKEN}:{};

const defaults={
 page:{size:"A4",left:52,right:52,top:132,bottom:82,auto_break:true,repeat_table_header:true},
 patient:{
  visible:["name","age","sex","code","uhid","referred_by","received_on","reported_on","phone"],
  labels:{name:"Patient Name",age_gender:"Age / Gender",code:"Patient ID",uhid:"UHID",referred_by:"Referred By",received_on:"Received On",reported_on:"Reported On",phone:"Phone"},
  columns:2,style:"card",font_size:8.5,spacing:12,line_spacing:1.25,row_gap:4,label_bold:true,
  width_percent:100,height:0,transparent:false,background:"#F5F6F8",background_opacity:100,
  title:"PATIENT INFORMATION",title_align:"left",title_size:9,title_style:"bold",title_color:"#151A2D",
  position:{x:0,y:0}
 },
 results:{
  columns:["name","value","unit","reference_range"],font_size:9,header_size:7.5,section_font_size:8,
  section_bold:true,section_style:"bold",section_align:"left",section_text:"#151A2D",
  section_background:"#ECEAFB",section_title:"EXAMINATION RESULTS",show_grid:false,row_spacing:5,
  report_title:"LABORATORY REPORT",report_title_align:"left",report_title_size:12,
  report_title_style:"bold",report_title_color:"#151A2D",report_title_line_color:"#5F52E8"
 },
 appearance:{text:"#151A2D",accent:"#5F52E8",font:"Helvetica"},
 manual:{header_text:"",footer_text:"",text_color:"#52606D",logo_path:""}
};

const merge=a=>({
 ...defaults,...a,
 page:{...defaults.page,...(a?.page||{})},
 patient:{...defaults.patient,...(a?.patient||{}),labels:{...defaults.patient.labels,...(a?.patient?.labels||{})}},
 results:{...defaults.results,...(a?.results||{})},
 appearance:{...defaults.appearance,...(a?.appearance||{})},
 manual:{...defaults.manual,...(a?.manual||{})}
});

const show=(m,hold=false)=>{
 const e=$("status");e.textContent=m;e.style.display="block";
 if(!hold)setTimeout(()=>e.style.display="none",2200);
};

async function api(url,opts={}){
 opts.headers={...(opts.headers||{}),...auth()};
 const r=await fetch(url,opts);const j=await r.json().catch(()=>({}));
 if(!r.ok)throw Error(j.detail||("Request failed ("+r.status+")"));return j;
}
function goBack(){location.href="/";}

function hexToRgba(hex,opacity){
 const h=String(hex||"#F5F6F8").replace("#","");
 if(!/^[0-9a-fA-F]{6}$/.test(h))return hex;
 const n=parseInt(h,16);
 return "rgba("+(n>>16)+","+((n>>8)&255)+","+(n&255)+","+Math.max(0,Math.min(100,Number(opacity)||0))/100+")";
}

const fieldDefs=[
 ["showName","name","Patient Name","Sample Patient"],
 ["showAge","age_gender","Age / Gender","32Y / M"],
 ["showCode","code","Patient ID","PT-001"],
 ["showUhid","uhid","UHID","UHID-001"],
 ["showRef","referred_by","Referred By","Dr. Example"],
 ["showReceived","received_on","Received On","01 Oct 2026"],
 ["showReported","reported_on","Reported On","01 Oct 2026"],
 ["showPhone","phone","Phone","+91 98xxxxxx"]
];

function buildFieldLabelInputs(){
 const grid=$(".field-labels")||$("fieldLabels");
 if(!grid)return;
 grid.innerHTML="";
 fieldDefs.forEach(([check,key,label])=>{
  const row=document.createElement("div");row.className="field-label-row";
  row.innerHTML='<input type="checkbox" id="'+check+'"><input type="text" id="label_'+key+'" aria-label="'+label+' label">';
  grid.appendChild(row);
 });
}

function syncLegacyChecks(){
 fieldDefs.forEach(([check,key,label])=>{
  const old=$(check);
  const row=$("label_"+key)?.parentElement;
  const newCheck=row?.querySelector("input[type=checkbox]");
  if(old&&newCheck){newCheck.checked=old.checked;old.style.display="none";old.parentElement.style.display="none";}
 });
}

function pagePoints(size){
 const sizes={A4:[595.2756,841.8898],A5:[419.5276,595.2756],LETTER:[612,792],LEGAL:[612,1008]};
 return sizes[String(size||"A4").toUpperCase()]||sizes.A4;
}
function applyPageGeometry(layout){
 const paper=$("paper"),overlay=$("overlay");if(!paper||!overlay)return;
 const [pw,ph]=pagePoints(layout.page?.size);
 const page=layout.page||{};
 const left=Math.max(0,Number(page.left)||0),right=Math.max(0,Number(page.right)||0);
 const top=Math.max(0,Number(page.top)||0),bottom=Math.max(0,Number(page.bottom)||0);
 const cssPerPt=96/72;
 const designW=(pw-left-right)*cssPerPt;
 const designH=(ph-top-bottom)*cssPerPt;
 const paperW=pw*cssPerPt;
 const paperH=ph*cssPerPt;
 paper.style.aspectRatio=pw+" / "+ph;
 overlay.style.left=(left/pw*100)+"%";
 overlay.style.right="auto";
 overlay.style.top=(top/ph*100)+"%";
 overlay.style.bottom="auto";
 overlay.style.width=designW+"px";
 overlay.style.height=designH+"px";
 const bodyScale=(paper.clientWidth||1)/(paperW||1);
 overlay.style.transform="scale("+bodyScale+")";
 overlay.dataset.scale=String(bodyScale);
}
function syncReportFlowPosition(layout){
 const p=layout.patient||{};
 const patient=$( "patientBlock"),flow=$( "reportFlow");
 if(!patient||!flow)return;
 const x=Number(p.position?.x)||0;
 const y=Number(p.position?.y)||0;
 const gap=7;
 const topSpacing=Math.max(0,Number(layout.page?.top_spacing ?? layout.patient?.top_spacing ?? layout.results?.top_spacing ?? 0)||0);
 // The patient keeps its normal layout height while its visual position is
 // translated. Start the report after that real height, plus the saved Y
 // offset and the same gap used by the PDF renderer.
 flow.style.transform="translate("+x+"px, "+(y+patient.offsetHeight+gap+topSpacing)+"px)";
}

function renderPreview(){
 const l=merge(settings.report_layout||{}),p=l.patient,r=l.results;
 applyPageGeometry(l);
 const pv=$("pvPatient");pv.innerHTML="";
 fieldDefs.forEach(([check,key,label,value])=>{
  const visible=p.visible.includes(key);
  if(!visible)return;
  const d=document.createElement("div");d.className="pv";
  d.innerHTML="<b>"+(p.labels[key]||label)+"</b><span>"+value+"</span>";
  pv.appendChild(d);
 });
 pv.style.gridTemplateColumns=$( "patientCols").value==="1"?"1fr":"1fr 1fr";
 pv.style.rowGap=(Number($( "patientRowGap").value)||0)+"px";
 const paper=$( "paper");paper.style.fontFamily=$( "font").value;paper.style.color=l.appearance.text||"#151A2D";
 const patient=$( "patientBlock"),flow=$( "reportFlow"),pos=p.position||{x:0,y:0};
 patient.style.transform="translate("+(Number(pos.x)||0)+"px, "+(Number(pos.y)||0)+"px)";
 syncReportFlowPosition(l);
 patient.style.width=(Number($( "patientWidth").value)||100)+"%";
 patient.style.minHeight=(Number($( "patientHeight").value)||0)+"px";
 patient.style.fontSize=$( "patientFont").value+"px";
 patient.style.lineHeight=$( "patientLineSpacing").value;
 patient.style.background=$( "patientTransparent").value==="true"?"transparent":hexToRgba($( "patientBg").value,$( "patientBgOpacity").value);
 patient.style.borderColor=p.style==="plain"?"transparent":"#E2E5EC";
 const pt=$( "pvPatientTitle");pt.textContent=p.title||"PATIENT INFORMATION";pt.style.textAlign=$( "patientTitleAlign").value;
 pt.style.fontSize=$( "patientTitleSize").value+"px";pt.style.color=$( "patientTitleColor").value;
 pt.style.fontWeight=["bold","bold_italic"].includes($( "patientTitleStyle").value)?"700":"400";
 pt.style.fontStyle=["italic","bold_italic"].includes($( "patientTitleStyle").value)?"italic":"normal";
 const rt=$( "reportTitleBlock");rt.textContent=($( "reportTitleText").value||"LABORATORY REPORT").toUpperCase();
 rt.style.textAlign=$( "reportTitleAlign").value;rt.style.fontSize=$( "reportTitleSize").value+"px";rt.style.color=$( "reportTitleColor").value;
 rt.style.fontWeight=["bold","bold_italic"].includes($( "reportTitleStyle").value)?"700":"400";
 rt.style.fontStyle=["italic","bold_italic"].includes($( "reportTitleStyle").value)?"italic":"normal";
 rt.style.borderBottomColor=$( "reportTitleLineColor").value;
 const sec=$( "reportSectionBlock");sec.textContent=($( "sectionTitleText").value||"EXAMINATION RESULTS").toUpperCase();
 sec.style.textAlign=$( "sectionAlign").value;sec.style.fontSize=$( "sectionSize").value+"px";sec.style.color=$( "sectionColor").value;
 sec.style.background=$( "sectionBg").value;
 sec.style.fontWeight=["bold","bold_italic"].includes($( "sectionStyle").value)?"700":"400";
 sec.style.fontStyle=["italic","bold_italic"].includes($( "sectionStyle").value)?"italic":"normal";
 document.querySelectorAll(".tr").forEach(x=>{x.style.fontSize=$("fontSize").value+"px";x.style.paddingTop=$( "rowSpacing").value+"px";x.style.paddingBottom=$( "rowSpacing").value+"px";x.style.border=$( "gridStyle").checked?"1px solid #dfe3ec":"";});
}

function collect(){
 const old=merge(settings.report_layout||{}),visible=[],labels={};
 fieldDefs.forEach(([check,key,label])=>{
  const c=$( "label_"+key)?.previousElementSibling;
  if(c?.checked)visible.push(key);
  labels[key]=($( "label_"+key)?.value||label).trim()||label;
 });
 return {...old,
  page:{...old.page,size:$( "pageSize").value,top:Number($( "reportTop").value),auto_break:$( "autoBreak").value==="true",repeat_table_header:$( "repeatHeader").value==="true"},
  patient:{...old.patient,visible,labels,columns:Number($( "patientCols").value),style:$( "patientStyle").value,font_size:Number($( "patientFont").value),spacing:Number($( "patientSpacing").value),line_spacing:Number($( "patientLineSpacing").value),row_gap:Number($( "patientRowGap").value),width_percent:Number($( "patientWidth").value),height:Number($( "patientHeight").value),transparent:$( "patientTransparent").value==="true",background:$( "patientBg").value,background_opacity:Number($( "patientBgOpacity").value),title:$( "patientTitleText")?.value||"PATIENT INFORMATION",title_align:$( "patientTitleAlign").value,title_size:Number($( "patientTitleSize").value),title_style:$( "patientTitleStyle").value,title_color:$( "patientTitleColor").value,position:{x:Number(old.patient?.position?.x)||0,y:Number(old.patient?.position?.y)||0}},
  results:{...old.results,font_size:Number($( "fontSize").value),section_font_size:Number($( "sectionSize").value),row_spacing:Number($( "rowSpacing").value),show_grid:$( "gridStyle").checked,section_bold:["bold","bold_italic"].includes($( "sectionStyle").value),section_style:$( "sectionStyle").value,section_align:$( "sectionAlign").value,section_text:$( "sectionColor").value,section_background:$( "sectionBg").value,section_title:$( "sectionTitleText").value.trim()||"EXAMINATION RESULTS",report_title:$( "reportTitleText").value.trim()||"LABORATORY REPORT",report_title_align:$( "reportTitleAlign").value,report_title_size:Number($( "reportTitleSize").value),report_title_style:$( "reportTitleStyle").value,report_title_color:$( "reportTitleColor").value,report_title_line_color:$( "reportTitleLineColor").value},
  appearance:{...old.appearance,font:$( "font").value}
 };
}

function enablePatientDrag(){
 const paper=$( "paper"),patient=$( "patientBlock");if(!paper||!patient||patient.dataset.dragReady==="1")return;
 patient.dataset.dragReady="1";patient.style.pointerEvents="auto";patient.style.touchAction="none";patient.style.cursor="grab";
 let dragging=false,pointerId=null,startX=0,startY=0,originX=0,originY=0;
 const apply=(x,y)=>{patient.style.transform="translate("+x+"px, "+y+"px)";$( "reportFlow").style.transform="translate(0px, "+y+"px)";};
 patient.addEventListener("pointerdown",e=>{if(e.button!==undefined&&e.button!==0)return;e.preventDefault();const pos=merge(settings.report_layout||{}).patient.position||{x:0,y:0};const rect=$("overlay").getBoundingClientRect();const scale=rect.width/Math.max(1,$("overlay").offsetWidth);patient.dataset.scale=String(scale||1);dragging=true;pointerId=e.pointerId;startX=e.clientX;startY=e.clientY;originX=Number(pos.x)||0;originY=Number(pos.y)||0;patient.style.cursor="grabbing";patient.setPointerCapture?.(e.pointerId);});
 patient.addEventListener("pointermove",e=>{if(!dragging||e.pointerId!==pointerId)return;e.preventDefault();const scale=Number(patient.dataset.scale)||1;apply(originX+(e.clientX-startX)/scale,originY+(e.clientY-startY)/scale);});
 const finish=e=>{if(!dragging||e.pointerId!==pointerId)return;const layout=merge(settings.report_layout||{});const scale=Number(patient.dataset.scale)||1;const x=originX+(e.clientX-startX)/scale,y=originY+(e.clientY-startY)/scale;layout.patient.position={x:Math.round(x*10)/10,y:Math.round(y*10)/10};settings.report_layout=layout;apply(layout.patient.position.x,layout.patient.position.y);dragging=false;pointerId=null;patient.style.cursor="grab";try{patient.releasePointerCapture?.(e.pointerId)}catch(_){}};
 patient.addEventListener("pointerup",finish);patient.addEventListener("pointercancel",finish);
}

async function showAuthenticatedTemplate(){try{const r=await fetch("/api/settings/template/preview?t="+Date.now(),{headers:auth(),cache:"no-store"});if(!r.ok)throw Error("Could not load template preview");const blob=await r.blob();if(templateObjectUrl)URL.revokeObjectURL(templateObjectUrl);templateObjectUrl=URL.createObjectURL(blob);$("templateBg").src=templateObjectUrl;$("templateBg").style.display="block";$("templateName").textContent="Uploaded letterhead";return true;}catch(e){$("templateBg").removeAttribute("src");$("templateBg").style.display="none";$("templateName").textContent="Template preview unavailable";return false;}}
async function uploadTemplate(){const f=$("templateFile").files[0];if(!f)return alert("Choose a PDF or Word letterhead first.");const fd=new FormData();fd.append("file",f);try{show("Uploading letterhead…",true);await api("/api/settings/template",{method:"POST",body:fd});await showAuthenticatedTemplate();$("templateName").textContent=f.name;show("Letterhead uploaded");}catch(e){show("Upload failed: "+e.message,true);}}
async function saveDesign(){try{show("Saving report design…",true);const layout=collect();const f=new URLSearchParams({whatsapp_enabled:String(settings.whatsapp_enabled||false),upi_id:String(settings.upi_id||""),report_layout:JSON.stringify(layout)});await api("/api/settings",{method:"PUT",body:f});settings.report_layout=layout;applyPageGeometry(layout);renderPreview();show("Report design saved");}catch(e){show("Save failed: "+e.message,true);}}
async function loadTemplate(){try{const r=await fetch("/api/settings/template",{headers:auth(),cache:"no-store"});if(r.ok)await showAuthenticatedTemplate();}catch(e){}}

async function init(){
 try{
  show("Loading report design…",true);settings=await api("/api/settings");const l=merge(settings.report_layout||{});
  buildFieldLabelInputs();
  $("pageSize").value=l.page.size||"A4";$("patientStyle").value=l.patient.style||"card";$("patientCols").value=l.patient.columns||2;$("patientFont").value=l.patient.font_size||8.5;$("patientSpacing").value=l.patient.spacing??12;
  $("patientWidth").value=l.patient.width_percent??100;$("patientHeight").value=l.patient.height??0;$("patientLineSpacing").value=l.patient.line_spacing??1.25;$("patientRowGap").value=l.patient.row_gap??4;$("patientBg").value=l.patient.background||"#F5F6F8";$("patientBgOpacity").value=l.patient.background_opacity??100;$("patientTransparent").value=String(!!l.patient.transparent);
  $("patientTitleAlign").value=l.patient.title_align||"left";$("patientTitleSize").value=l.patient.title_size||9;$("patientTitleStyle").value=l.patient.title_style||"bold";$("patientTitleColor").value=l.patient.title_color||"#151A2D";
  $("font").value=l.appearance.font||"Helvetica";$("fontSize").value=l.results.font_size||9;$("sectionSize").value=l.results.section_font_size||8;$("rowSpacing").value=l.results.row_spacing??5;$("gridStyle").checked=!!l.results.show_grid;
  $("sectionAlign").value=l.results.section_align||"left";$("sectionStyle").value=l.results.section_style|| (l.results.section_bold===false?"normal":"bold");$("sectionColor").value=l.results.section_text||"#151A2D";$("sectionBg").value=l.results.section_background||"#ECEAFB";$("sectionTitleText").value=l.results.section_title||"EXAMINATION RESULTS";
  $("reportTitleText").value=l.results.report_title||"LABORATORY REPORT";$("reportTitleAlign").value=l.results.report_title_align||"left";$("reportTitleSize").value=l.results.report_title_size||12;$("reportTitleStyle").value=l.results.report_title_style||"bold";$("reportTitleColor").value=l.results.report_title_color||"#151A2D";$("reportTitleLineColor").value=l.results.report_title_line_color||"#5F52E8";
  fieldDefs.forEach(([check,key,label])=>{$(check).checked=l.patient.visible.includes(key);$("label_"+key).value=l.patient.labels[key]||label;});syncLegacyChecks();
  $("autoBreak").value=String(l.page.auto_break!==false);$("repeatHeader").value=String(l.page.repeat_table_header!==false);$("reportTop").value=l.page.top||132;
  const ids=["patientStyle","patientCols","patientFont","patientSpacing","patientWidth","patientHeight","patientLineSpacing","patientRowGap","patientBg","patientBgOpacity","patientTransparent","patientTitleAlign","patientTitleSize","patientTitleStyle","patientTitleColor","font","fontSize","sectionSize","rowSpacing","gridStyle","sectionAlign","sectionStyle","sectionColor","sectionBg","sectionTitleText","reportTitleText","reportTitleAlign","reportTitleSize","reportTitleStyle","reportTitleColor","reportTitleLineColor","pageSize","autoBreak","repeatHeader","reportTop"];
  fieldDefs.forEach(([check,key])=>ids.push(check,"label_"+key));
  ids.forEach(id=>$(id)?.addEventListener("input",renderPreview));ids.forEach(id=>$(id)?.addEventListener("change",renderPreview));
  await loadTemplate();renderPreview();enablePatientDrag();show("Report design ready");
 }catch(e){show("Could not load report design: "+e.message,true);}
}
window.addEventListener("resize",()=>{const l=merge(settings.report_layout||{});applyPageGeometry(l);syncReportFlowPosition(l);});\ninit();