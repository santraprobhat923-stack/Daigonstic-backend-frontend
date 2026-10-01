const TOKEN=(()=>{try{return localStorage.getItem("aarogyam_token")||""}catch(e){return""}})();
let settings={};
const $=id=>document.getElementById(id);
const auth=()=>TOKEN?{Authorization:"Bearer "+TOKEN}:{};
const show=(m,hold=false)=>{const e=$("status");e.textContent=m;e.style.display="block";if(!hold)setTimeout(()=>e.style.display="none",2200)};
async function api(url,opts={}){opts.headers={...(opts.headers||{}),...auth()};const r=await fetch(url,opts);const j=await r.json().catch(()=>({}));if(!r.ok)throw Error(j.detail||("Request failed ("+r.status+")"));return j}
function goBack(){location.href="/"}
const defaults={page:{size:"A4",left:52,right:52,top:132,bottom:82},patient:{visible:["name","age","sex","code","uhid","referred_by","received_on","reported_on","phone"],order:["name","age_gender","code","uhid","referred_by","received_on","reported_on","phone"],columns:2,style:"card",font_size:8.5,label_bold:true,background:"#F5F6F8",border:"#E2E5EC"},results:{columns:["name","value","unit","reference_range"],section_order:[],section_align:"left",section_bold:true,section_font_size:7.9,section_text:"#151A2D",section_padding:5,section_headers:true,section_background:"#ECEAFB",table_header_background:"#F7F7FA",font_size:9,header_size:7.5,show_grid:false},appearance:{text:"#151A2D",accent:"#5F52E8",font:"Helvetica"},manual:{header_text:"",footer_text:"",text_color:"#52606D",logo_path:""}};
function merge(a){return {...defaults,...a,page:{...defaults.page,...(a?.page||{})},patient:{...defaults.patient,...(a?.patient||{})},results:{...defaults.results,...(a?.results||{})},appearance:{...defaults.appearance,...(a?.appearance||{})},manual:{...defaults.manual,...(a?.manual||{})}}}
function set(id,v){$(id).value=v}
function renderPreview(){
  const name=$("centreName").value||"Your Diagnostic Centre", phone=$("phone").value, contact=$("contact").value, address=$("address").value;
  $("pvName").textContent=name;$("pvMeta").innerHTML=[phone,contact,address].filter(Boolean).join(" · ").replace(/\n/g,"<br>");
  $("pvFooter").textContent=$("footer").value||"Page footer / centre information";
  const p=$("pvPatient");p.innerHTML="";
  const fields=[["showName","Patient Name","Sample Patient"],["showAge","Age / Gender","32Y / M"],["showCode","Patient ID","PT-001"],["showUhid","UHID","UHID-001"],["showRef","Referred By","Dr. Example"],["showReceived","Received On","01 Oct 2026"],["showReported","Reported On","01 Oct 2026"],["showPhone","Phone","+91 98xxxxxx"]];
  fields.filter(x=>$(x[0]).checked).forEach(x=>{const d=document.createElement("div");d.className="pv";d.innerHTML="<b>"+x[1]+"</b><span>"+x[2]+"</span>";p.appendChild(d)});
  p.style.gridTemplateColumns=$("patientCols").value==="1"?"1fr":"1fr 1fr";
  $("paper").style.color=$("bodyText").value;$("paper").style.fontFamily=$("font").value;
  $("pvName").style.fontSize=Math.max(14,Number($("fontSize").value)+9)+"px";
  $("pvName").style.color=$("textColor").value;$("pvTitle").style.borderColor=$("accent").value;
  document.querySelector(".patient").style.background=$("patientBg").value;document.querySelector(".section").style.background=$("sectionBg").value;
  document.querySelector(".table").style.fontFamily=$("font").value;
}
function collect(){
  const visible=[];const map={showName:"name",showAge:"age",showCode:"code",showUhid:"uhid",showRef:"referred_by",showReceived:"received_on",showReported:"reported_on",showPhone:"phone"};for(const [id,key] of Object.entries(map))if($(id).checked)visible.push(key);
  const old=settings.report_layout||{};const logo=old.manual||{};
  const header=[$("centreName").value,$("address").value,$("phone").value,$("contact").value].filter(Boolean).join("\n");
  return {...merge(old),page:{...merge(old).page,auto_break:$("autoBreak").value==="true",repeat_table_header:$("repeatHeader").value==="true"},patient:{...merge(old).patient,visible,columns:Number($("patientCols").value),style:$("patientStyle").value,background:$("patientBg").value},results:{...merge(old).results,font_size:Number($("fontSize").value),show_grid:$("gridStyle").value==="true",section_background:$("sectionBg").value},appearance:{text:$("bodyText").value,accent:$("accent").value,font:$("font").value},manual:{...logo,header_text:header,footer_text:$("footer").value,text_color:$("textColor").value,logo_position:$("logoPos").value,logo_width:Number($("logoWidth").value)}}
}
async function uploadLogo(){
  const f=$("logo").files[0];if(!f)return;
  const fd=new FormData();fd.append("file",f);show("Uploading logo…",true);
  await api("/api/settings/logo",{method:"POST",body:fd});show("Logo uploaded");const img=$("previewLogo");img.src="/api/settings/logo?t="+Date.now();img.style.display="block";positionLogo();
}
function positionLogo(){const p=$("logoPos").value;const img=$("previewLogo");img.style.width=$("logoWidth").value+"px";img.style.margin=p==="center"?"0 auto":p==="right"?"0 0 0 auto":"0"}
async function saveDesign(){
  try{show("Saving report design…",true);const layout=collect();const f=new URLSearchParams({whatsapp_enabled:String(settings.whatsapp_enabled||false),upi_id:String(settings.upi_id||""),report_layout:JSON.stringify(layout)});await api("/api/settings",{method:"PUT",body:f});settings.report_layout=layout;show("Report design saved")}catch(e){show("Save failed: "+e.message,true)}
}
async function init(){
  try{show("Loading report design…",true);settings=await api("/api/settings");const l=merge(settings.report_layout||{});const m=l.manual||{};
    set("centreName",(m.header_text||"").split("\n")[0]||"");set("address",(m.header_text||"").split("\n")[1]||"");set("phone",(m.header_text||"").split("\n")[2]||"");set("contact",(m.header_text||"").split("\n")[3]||"");
    set("logoPos",m.logo_position||"left");set("logoWidth",m.logo_width||90);set("textColor",m.text_color||l.appearance.text);set("font",l.appearance.font);set("fontSize",l.results.font_size);set("accent",l.appearance.accent);set("bodyText",l.appearance.text);set("patientBg",l.patient.background);set("sectionBg",l.results.section_background);set("patientStyle",l.patient.style);set("patientCols",l.patient.columns);set("gridStyle",String(!!l.results.show_grid));set("autoBreak",String(l.page.auto_break!==false));set("repeatHeader",String(l.page.repeat_table_header!==false));set("footer",m.footer_text||"");
    const map={showName:"name",showAge:"age",showCode:"code",showUhid:"uhid",showRef:"referred_by",showReceived:"received_on",showReported:"reported_on",showPhone:"phone"};for(const [id,key] of Object.entries(map))$(id).checked=(l.patient.visible||[]).includes(key);
    if(m.logo_path){const img=$("previewLogo");img.src="/api/settings/logo?t="+Date.now();img.style.display="block"}renderPreview();positionLogo();
    ["centreName","phone","contact","address","logoPos","logoWidth","textColor","patientStyle","patientCols","font","fontSize","accent","bodyText","patientBg","sectionBg","gridStyle","autoBreak","repeatHeader","footer","showName","showAge","showCode","showUhid","showRef","showReceived","showReported","showPhone"].forEach(id=>$(id).addEventListener("input",renderPreview));
    $("logoPos").addEventListener("change",()=>{renderPreview();positionLogo()});$("logoWidth").addEventListener("input",positionLogo);$("logo").addEventListener("change",uploadLogo);
  }catch(e){show("Could not load report design: "+e.message,true)}
}
init();