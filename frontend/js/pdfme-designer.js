const TOKEN=(()=>{try{return localStorage.getItem("aarogyam_token")||""}catch(e){return""}})();
const statusEl=document.getElementById("status");
let designer=null, currentSettings=null;
const show=(msg,hold=false)=>{statusEl.textContent=msg;statusEl.style.display="block";if(!hold)setTimeout(()=>statusEl.style.display="none",2200)};
const auth=()=>TOKEN?{Authorization:"Bearer "+TOKEN}:{};
async function api(url,opts={}){opts.headers={...(opts.headers||{}),...auth()};const r=await fetch(url,opts);const j=await r.json().catch(()=>({}));if(!r.ok)throw Error(j.detail||("Request failed ("+r.status+")"));return j}
function goBack(){location.href="/"}
function sampleTemplate(basePdf){
  return {
    basePdf,
    schemas:[[
      {name:"patient_name",type:"text",content:"Patient Name",position:{x:18,y:65},width:78,height:8,fontSize:11,bold:true},
      {name:"patient_age_gender",type:"text",content:"Age / Gender",position:{x:100,y:65},width:45,height:8,fontSize:10},
      {name:"patient_id",type:"text",content:"Patient ID",position:{x:150,y:65},width:42,height:8,fontSize:10},
      {name:"report_date",type:"text",content:"Report Date",position:{x:18,y:75},width:55,height:8,fontSize:9},
      {name:"results_table",type:"table",content:"[[\"Parameter\",\"Result\",\"Unit\",\"Reference Range\"],[\"Sample parameter\",\"—\",\"—\",\"—\"]]",position:{x:18,y:88},width:174,height:85,showHead:true,head:["Parameter","Result","Unit","Reference Range"],headWidthPercentages:[38,20,15,27],tableStyles:{borderWidth:0.3,borderColor:"#999999"},headStyles:{fontSize:8,fontColor:"#ffffff",backgroundColor:"#555b72",padding:{top:3,right:3,bottom:3,left:3}},bodyStyles:{fontSize:8,fontColor:"#222222",padding:{top:3,right:3,bottom:3,left:3},borderWidth:{top:0.1,right:0.1,bottom:0.1,left:0.1},borderColor:"#dddddd"}}
    ]]
  };
}
async function loadBasePdf(){
  try{
    const r=await fetch("/api/settings/template?preview="+Date.now(),{headers:auth()});
    if(r.ok){const b=await r.arrayBuffer();return new Uint8Array(b)}
  }catch(e){}
  return {width:210,height:297,padding:[12,12,12,12]};
}
async function init(){
  try{
    show("Loading master template…",true);
    const [{Designer},{text,image,signature,table},{},settings]=await Promise.all([
      import("/pdfme/@pdfme/ui@6.1.12?bundle"),
      import("/pdfme/@pdfme/schemas@6.1.12?bundle"),
      import("/pdfme/@pdfme/common@6.1.12?bundle"),
      api("/api/settings")
    ]);
    currentSettings=settings;
    const saved=settings.report_layout?.pdfme_template;
    const basePdf=await loadBasePdf();
    const template=saved?.schemas ? {...saved,basePdf} : sampleTemplate(basePdf);
    designer=new Designer({
      domContainer:document.getElementById("designer"),
      template,
      plugins:{text,image,signature,Table:table},
      options:{sidebarOpen:true,zoomLevel:1,theme:{token:{colorPrimary:"#6d5dfc"}}}
    });
    statusEl.style.display="none";
  }catch(e){
    console.error(e);
    show("Designer could not load: "+(e.message||e),true);
  }
}
async function saveTemplate(){
  if(!designer)return;
  try{
    show("Saving master template…",true);
    const t=designer.getTemplate();
    const safe={...t};
    delete safe.basePdf;
    const old=currentSettings?.report_layout||{};
    const layout={...old,pdfme_template:safe,designer_engine:"pdfme",template_mode:"template"};
    const f=new URLSearchParams({whatsapp_enabled:String(currentSettings?.whatsapp_enabled||false),upi_id:String(currentSettings?.upi_id||""),report_layout:JSON.stringify(layout)});
    await api("/api/settings",{method:"PUT",body:f});
    show("Master template saved");
  }catch(e){show("Save failed: "+(e.message||e),true)}
}
window.goBack=goBack;window.saveTemplate=saveTemplate;init();