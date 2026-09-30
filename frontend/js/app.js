let token="",me=null,currentPage="dashboard";
try{token=localStorage.getItem("aarogyam_token")||""}catch(e){token=""}
const app=document.getElementById("app");
const esc=x=>String(x??"").replace(/[&<>"]/g,m=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[m]));
async function api(u,o={}){o.headers={...(o.headers||{}),...(token?{Authorization:"Bearer "+token}:{})};const r=await fetch(u,o);const j=await r.json().catch(()=>({}));if(!r.ok)throw Error(j.detail||("Request failed ("+r.status+")"));return j}
function showError(e){app.innerHTML='<div class="login-page"><div class="card login-card"><div class="login-brand"><span class="brand-mark">✚</span>Aarogyam</div><h2>Workspace could not load</h2><p class="muted">'+esc(e?.message||e)+'</p><button class="primary" onclick="login()">Open Login</button></div></div>'}
async function downloadPDF(id){try{const r=await fetch("/api/reports/"+id+"/download",{headers:{Authorization:"Bearer "+token}});if(!r.ok)throw Error("PDF download failed");const b=await r.blob(),u=URL.createObjectURL(b),a=document.createElement("a");a.href=u;a.download="Aarogyam_Report_"+id+".pdf";document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(u),1000)}catch(e){alert(e.message)}}
const nav=()=>'<aside class="sidebar"><div class="brand"><span class="brand-mark">✚</span>Aarogyam</div><div class="side-label">Workspace</div><div class="side-nav">'+[["dashboard","⌂","Dashboard","dash()"],["capture","＋","New Report","capture()"],["pending","◷","Pending Verification","pending()"],["reports","▤","Reports","reports()"],["notes","●","Notifications","notes()"]].map(x=>'<button class="'+(currentPage===x[0]?"active":"")+'" onclick="'+x[3]+'"><span class="ico">'+x[1]+"</span>"+x[2]+"</button>").join("")+'</div><div class="side-label">Administration</div><div class="side-nav"><button class="'+(currentPage==="credits"?"active":"")+'" onclick="credits()"><span class="ico">₹</span>Credits & Recharge</button><button class="'+(currentPage==="settings"?"active":"")+'" onclick="settings()"><span class="ico">⚙</span>Centre Settings</button></div><div class="side-bottom"><div class="side-nav"><button onclick="logout()"><span class="ico">↪</span>Sign out</button></div></div></aside><div class="mobile-drawer-backdrop" id="drawerBackdrop" onclick="closeSidebar()"></div><aside class="mobile-sidebar" id="mobileSidebar"><div class="mobile-sidebar-head"><div class="brand"><span class="brand-mark">✚</span>Aarogyam</div><button class="drawer-close" onclick="closeSidebar()">×</button></div><div class="side-label">Workspace</div><div class="side-nav">'+[["dashboard","⌂","Dashboard","dash()"],["capture","＋","New Report","capture()"],["pending","◷","Pending Verification","pending()"],["reports","▤","Reports","reports()"],["notes","●","Notifications","notes()"]].map(x=>'<button class="'+(currentPage===x[0]?"active":"")+'" onclick="'+x[3]+';closeSidebar()"><span class="ico">'+x[1]+"</span>"+x[2]+"</button>").join("")+'</div><div class="side-label">Administration</div><div class="side-nav"><button class="'+(currentPage==="credits"?"active":"")+'" onclick="credits();closeSidebar()"><span class="ico">₹</span>Credits & Recharge</button><button class="'+(currentPage==="settings"?"active":"")+'" onclick="settings();closeSidebar()"><span class="ico">⚙</span>Centre Settings</button><button onclick="logout()"><span class="ico">↪</span>Sign out</button></div></aside><div class="main-menu-button"><button onclick="openSidebar()" aria-label="Open menu">☰</button></div>';function openSidebar(){document.getElementById("mobileSidebar")?.classList.add("open");document.getElementById("drawerBackdrop")?.classList.add("open");document.body.classList.add("drawer-open")}
function closeSidebar(){document.getElementById("mobileSidebar")?.classList.remove("open");document.getElementById("drawerBackdrop")?.classList.remove("open");document.body.classList.remove("drawer-open")}
function shell(body){return nav()+'<div class="main"><header class="topbar"><div class="topbar-brand"><span class="brand-mark">✚</span>Aarogyam</div><div class="top-user"><div class="user-copy"><b>'+esc(me?.name||"Centre")+'</b><br><small>Centre workspace</small></div><div class="avatar">'+esc((me?.name||"C").charAt(0).toUpperCase())+"</div></div></header>"+body+"</div>"}
function login(){app.innerHTML='<div class="login-page"><div class="card login-card"><div class="login-brand"><span class="brand-mark">✚</span>Aarogyam</div><p class="eyebrow">Diagnostic centre workspace</p><h2>Sign in</h2><p class="muted">Manage reports, verification and patient delivery from one place.</p><div class="field"><label>EMAIL ADDRESS</label><input id="email" autocomplete="username"></div><div class="field"><label>PASSWORD</label><input id="password" type="password" autocomplete="current-password"></div><button class="primary" onclick="doLogin()">Sign in to workspace</button><button class="login-secondary" onclick="createCentre()">Create centre</button></div></div>'}
async function doLogin(){try{const j=await api("/api/login",{method:"POST",body:new URLSearchParams({email:document.getElementById("email").value,password:document.getElementById("password").value})});token=j.access_token;localStorage.setItem("aarogyam_token",token);await boot()}catch(e){alert(e.message)}}
async function createCentre(){const name=prompt("Centre name"),email=prompt("Email"),password=prompt("Password");if(!name||!email||!password)return;try{const j=await api("/api/bootstrap",{method:"POST",body:new URLSearchParams({name,email,password})});token=j.access_token;localStorage.setItem("aarogyam_token",token);await boot()}catch(e){alert(e.message)}}
function logout(){localStorage.removeItem("aarogyam_token");token="";me=null;login()}
async function boot(){if(!token)return login();try{me=await api("/api/me");await dash()}catch(e){localStorage.removeItem("aarogyam_token");token="";showError(e)}}
async function dash(){currentPage="dashboard";const r=await api("/api/reports");const pending=r.filter(x=>String(x.status||"").toUpperCase()!=="VERIFIED"&&String(x.status||"").toUpperCase()!=="GENERATED").length;const generated=r.filter(x=>x.pdf_path).length;app.innerHTML=shell('<div class="wrap"><div class="page-head"><div><div class="eyebrow">Centre operations</div><h1>Good day, '+esc(me?.name||"Centre")+'</h1><p>Keep your diagnostic reports moving from capture to delivery.</p></div><div class="actions"><button class="primary" onclick="capture()">＋ New report</button></div></div><div class="grid"><div class="card kpi kpi-blue"><div class="eyebrow">Total reports</div><div class="num">'+r.length+'</div><div class="sub">All centre reports</div></div><div class="card kpi kpi-green"><div class="eyebrow">PDF ready</div><div class="num">'+generated+'</div><div class="sub">Available to download</div></div><div class="card kpi kpi-amber"><div class="eyebrow">In workflow</div><div class="num">'+pending+'</div><div class="sub">Reports needing action</div></div><div class="card kpi kpi-slate"><div class="eyebrow">Credits</div><div class="num">'+esc(me?.credits??0)+'</div><div class="sub">Available report credits</div></div></div><div class="dashboard-chart-row"><div class="card chart-card"><div class="chart-head"><div><h3>Report activity</h3><p class="muted">Recent centre activity</p></div><span class="chart-pill">LIVE</span></div><div class="chart-wrap"><div class="chart-y"><span>High</span><span>Mid</span><span>Low</span></div><div class="fake-chart" aria-label="Report activity graph"><i style="height:34%"></i><i style="height:48%"></i><i style="height:40%"></i><i style="height:62%"></i><i style="height:55%"></i><i style="height:76%"></i><i style="height:88%"></i></div></div><div class="chart-footer"><span>Earlier</span><span>Now</span></div></div><div class="card insight-card"><div class="eyebrow">Workflow health</div><div class="health-ring"><div><strong>'+generated+'</strong><span>PDF ready</span></div></div><div class="health-list"><div><span class="dot dot-purple"></span>All reports <b>'+r.length+'</b></div><div><span class="dot dot-green"></span>Generated <b>'+generated+'</b></div><div><span class="dot dot-amber"></span>Action needed <b>'+pending+'</b></div></div></div></div><div class="dashboard-chart-row"><div class="card chart-card"><div class="chart-head"><div><h3>Report activity</h3><p class="muted">Recent centre activity</p></div><span class="chart-pill">LIVE</span></div><div class="chart-wrap"><div class="chart-y"><span>High</span><span>Mid</span><span>Low</span></div><div class="fake-chart"><i style="height:34%"></i><i style="height:48%"></i><i style="height:40%"></i><i style="height:62%"></i><i style="height:55%"></i><i style="height:76%"></i><i style="height:88%"></i></div></div><div class="chart-footer"><span>Earlier</span><span>Now</span></div></div><div class="card insight-card"><div class="eyebrow">Workflow health</div><div class="health-ring"><div><strong>LIVE</strong><span>PDF ready</span></div></div><div class="health-list"><div><span class="dot dot-purple"></span>Captured</div><div><span class="dot dot-green"></span>Generated</div><div><span class="dot dot-amber"></span>Action needed</div></div></div></div><div class="two-col"><div class="card"><div class="page-head" style="margin-bottom:12px"><div><h3>Recent reports</h3><p class="muted">Latest activity in this centre</p></div><button onclick="reports()">View all</button></div>'+rows(r.slice(0,7))+'</div><div class="card"><h3>Quick actions</h3><div class="quick-grid"><button class="quick" onclick="capture()"><strong>Capture report</strong><span>Upload analyzer images for OCR</span></button><button class="quick" onclick="reports()"><strong>Find a report</strong><span>Search patient or report ID</span></button><button class="quick" onclick="settings()"><strong>Centre settings</strong><span>WhatsApp, UPI & template</span></button><button class="quick" onclick="notes()"><strong>Notifications</strong><span>See patient delivery activity</span></button></div></div></div><div class="card"><h3>Report workflow</h3><div class="workflow"><span class="step">1 · Capture</span><span class="arrow">→</span><span class="step">2 · OCR</span><span class="arrow">→</span><span class="step">3 · Verify</span><span class="arrow">→</span><span class="step">4 · PDF</span><span class="arrow">→</span><span class="step">5 · Deliver</span></div></div></div>')}
async function credits(){
  currentPage="credits";
  try{
    const s=await api("/api/credits");
    const rows=s.transactions||[];
    app.innerHTML=shell('<div class="wrap"><div class="page-head"><div><div class="eyebrow">Account balance</div><h1>Credits & Recharge</h1><p>Recharge report credits securely through Razorpay UPI.</p></div></div><div class="grid"><div class="card kpi kpi-slate"><div class="eyebrow">Available credits</div><div class="num" id="creditBalance">'+esc(s.balance)+'</div><div class="sub">1 credit is used when a report is generated</div></div><div class="card kpi kpi-blue"><div class="eyebrow">Current price</div><div class="num">₹'+esc(Number(s.price_inr).toFixed(2))+'</div><div class="sub">per report credit</div></div></div><div class="two-col"><div class="card"><h3>Recharge credits</h3><p class="muted">Choose a package or enter your own quantity. Payment opens in Razorpay Checkout and UPI is supported there.</p><div class="quick-grid">'+[100,250,500,1000].map(n=>'<button class="quick" onclick="startRecharge('+n+')"><strong>'+n+' credits</strong><span>₹'+(n*Number(s.price_inr)).toFixed(2)+'</span></button>').join("")+'</div><div class="field" style="margin-top:18px"><label>CUSTOM CREDIT QUANTITY</label><input id="customCredits" type="number" min="1" step="1" placeholder="e.g. 750"></div><button class="primary" onclick="startRecharge(Number(document.getElementById(\'customCredits\').value))">Recharge custom quantity</button><div id="rechargeStatus" class="upload-status" role="status" aria-live="polite"><span>✓</span><div><b>Secure payment</b><small>Credits are added only after the server verifies the Razorpay payment.</small></div></div></div><div class="card"><h3>Credit history</h3><div class="table-wrap"><table class="table"><thead><tr><th>Date</th><th>Type</th><th>Credits</th><th>Amount</th></tr></thead><tbody>'+(rows.length?rows.map(t=>'<tr><td>'+esc(new Date(t.created_at).toLocaleString())+'</td><td>'+esc(t.type)+'</td><td><b>'+(t.credits>0?"+":"")+esc(t.credits)+'</b></td><td>'+(t.amount_inr?("₹"+Number(t.amount_inr).toFixed(2)):"—")+'</td></tr>').join(""):'<tr><td colspan="4" class="muted">No credit transactions yet.</td></tr>')+'</tbody></table></div></div></div></div>');
  }catch(e){showError(e)}
}
async function startRecharge(quantity){
  quantity=Math.floor(Number(quantity));
  if(!quantity||quantity<1)return alert("Enter a valid credit quantity");
  const status=document.getElementById("rechargeStatus");
  if(status)status.innerHTML='<span>…</span><div><b>Preparing secure payment…</b><small>Creating your Razorpay order.</small></div>';
  try{
    if(typeof Razorpay==="undefined")throw Error("Razorpay Checkout could not load. Refresh the page and try again.");
    const f=new URLSearchParams({credits:String(quantity)});
    const o=await api("/api/credits/razorpay/order",{method:"POST",body:f});
    const options={key:o.key_id,amount:o.amount,currency:o.currency,name:"Aarogyam",description:quantity+" report credits",order_id:o.order_id,theme:{color:"#635bff"},
      handler:async function(response){
        try{
          if(status)status.innerHTML='<span>…</span><div><b>Verifying payment…</b><small>Do not close this page.</small></div>';
          const vf=new URLSearchParams({order_id:response.razorpay_order_id,payment_id:response.razorpay_payment_id,signature:response.razorpay_signature});
          const v=await api("/api/credits/razorpay/verify",{method:"POST",body:vf});
          me.credits=v.credits;
          if(status)status.innerHTML='<span>✓</span><div><b>Recharge successful</b><small>'+esc(v.message)+'</small></div>';
          await credits();
        }catch(e){alert(e.message);credits()}
      },
      modal:{ondismiss:function(){if(status)status.innerHTML='<span>!</span><div><b>Payment cancelled</b><small>No credits were added.</small></div>'}}
    };
    new Razorpay(options).open();
  }catch(e){if(status)status.innerHTML='<span>!</span><div><b>Recharge could not start</b><small>'+esc(e.message)+'</small></div>';alert(e.message)}
}
let intakeFiles=[];
function capture(){currentPage="capture";intakeFiles=[];app.innerHTML=shell('<div class="wrap"><div class="page-head"><div><div class="eyebrow">Report intake</div><h1>New report</h1><p>Take photos or choose report images. You can collect several slips before starting OCR.</p></div></div><div class="card"><div class="upload-zone"><div class="upload-icon">▣</div><h3>Capture diagnostic report</h3><p class="muted">Use the centre phone camera for a fresh slip, or choose existing images from the gallery.</p><div class="capture-actions"><button type="button" class="primary" onclick="openCamera()">📷 Take Photo</button><button type="button" onclick="openGallery()">📁 Choose from Gallery</button></div><input id="cameraInput" type="file" accept="image/*" capture="environment" hidden onchange="addCameraFile(this.files[0]);this.value="""><input id="imgs" type="file" accept="image/*" multiple hidden onchange="addGalleryFiles(this.files)"><div id="selectedFiles" class="selected-files" aria-live="polite">No images selected yet.</div><div id="selectedFileList" class="selected-file-list"></div><button id="uploadStartBtn" class="primary" onclick="upload()" disabled>Upload & start OCR</button><div id="uploadStatus" class="upload-status" role="status" aria-live="polite"><span class="upload-ready">✓</span><div><b>Ready</b><small>Add one or more report images. OCR starts after you tap Upload & start OCR.</small></div></div></div><p class="footer-note">OCR is draft data. A technician reviews and approves every report before it is finalized.</p></div></div>')}
function openCamera(){document.getElementById("cameraInput")?.click()}
function openGallery(){document.getElementById("imgs")?.click()}
function addCameraFile(file){if(file)appendIntakeFiles([file])}
function addGalleryFiles(files){appendIntakeFiles([...(files||[])])}
function appendIntakeFiles(files){const seen=new Set(intakeFiles.map(f=>f.name+"|"+f.size+"|"+f.lastModified));for(const f of files){if(!f||!f.type?.startsWith("image/"))continue;const key=f.name+"|"+f.size+"|"+f.lastModified;if(!seen.has(key)){intakeFiles.push(f);seen.add(key)}}renderSelectedFiles()}
function removeIntakeFile(i){intakeFiles.splice(i,1);renderSelectedFiles()}
function renderSelectedFiles(){const count=intakeFiles.length,el=document.getElementById("selectedFiles"),list=document.getElementById("selectedFileList"),btn=document.getElementById("uploadStartBtn");if(el)el.textContent=count?(count+" image"+(count===1?"":"s")+" ready to upload"):"No images selected yet.";if(btn)btn.disabled=!count;if(list)list.innerHTML=intakeFiles.map((f,i)=>'<div class="selected-file"><span><b>'+esc(f.name)+'</b><small>'+Math.max(1,Math.round(f.size/1024))+' KB</small></span><button type="button" aria-label="Remove '+esc(f.name)+'" onclick="removeIntakeFile('+i+')">×</button></div>').join("")}
function setUploadStatus(title, message, kind="ready") {
  const el=document.getElementById("uploadStatus");
  if(!el) return;
  const icon=kind==="success"?"✓":kind==="error"?"!":"…";
  el.innerHTML='<span>'+icon+'</span><div><b>'+esc(title)+'</b><small>'+esc(message)+'</small></div>';
}
async function upload(){
  const btn=document.querySelector("#uploadStartBtn");
  if(!intakeFiles.length)return alert("Add at least one report image");
  const files=[...intakeFiles];const f=new FormData();
  files.forEach(x=>f.append("files",x));
  if(btn)btn.disabled=true;
  setUploadStatus("Uploading slip…","Creating the report job. OCR will continue in the background.");
  try{
    const j=await api("/api/reports/upload",{method:"POST",body:f});
    const dup=j.duplicate_count||0,added=j.uploaded_count||files.length;
    const createdReports=j.reports||[j.report];
    const ids=createdReports.map(x=>"#"+x.id).join(", ");
    setUploadStatus(
      createdReports.length+" report job"+(createdReports.length===1?"":"s")+" created.",
      ids+" "+(createdReports.length===1?"is":"are")+" being read by OCR in the background. You can upload more slips now.",
      "success"
    );
    if(dup)setUploadStatus(
      createdReports.length+" report job"+(createdReports.length===1?"":"s")+" created.",
      ids+" · "+added+" new image"+(added===1?"":"s")+", "+dup+" duplicate"+(dup===1?"":"s")+" skipped.",
      "success"
    );
    setTimeout(()=>pending(),450);
    intakeFiles=[];
  }catch(e){
    setUploadStatus("Upload could not be completed.",e.message||"Please try the image again.","error");
    if(btn)btn.disabled=false;
  }
}
async function pending(){
  currentPage="pending";
  const r=await api("/api/reports");
  const jobs=r.filter(x=>["OCR_PROCESSING","OCR_REVIEW"].includes(String(x.status||"").toUpperCase()));
  app.innerHTML=shell('<div class="wrap"><div class="page-head"><div><div class="eyebrow">Technician queue</div><h1>Pending verification</h1><p>Upload many slips first, then review them here as OCR finishes.</p></div><div class="actions"><button class="primary" onclick="capture()">＋ Upload more</button></div></div><div class="card"><div id="pendingList">'+pendingRows(jobs)+'</div></div></div>');
  if(jobs.some(x=>String(x.status||"").toUpperCase()==="OCR_PROCESSING"))setTimeout(pending,1600);
}
async function verifyJob(id){
  try{
    const r=await api("/api/reports");
    const x=r.find(v=>v.id===id);
    if(!x)return alert("Report no longer exists");
    if(String(x.status||"").toUpperCase()==="OCR_PROCESSING")return pending();
    verify(id,x.verified_data||{patient:{},tests:[]});
  }catch(e){alert(e.message)}
}
function pendingRows(r){
  if(!r.length)return '<div class="empty-state"><h3>Queue is clear</h3><p class="muted">New uploaded slips will appear here when they are ready for technician verification.</p><button class="primary" onclick="capture()">＋ Upload reports</button></div>';
  return '<div class="pending-list">'+r.map(x=>{
    const processing=String(x.status||"").toUpperCase()==="OCR_PROCESSING";
    return '<div class="pending-item"><div class="pending-main"><span class="pending-id">#'+x.id+'</span><div><b>'+esc(x.patient_name||"Patient details pending OCR")+'</b><p class="muted">'+(processing?"OCR is reading the analyzer slip…":"OCR complete · review required")+'</p></div></div><div class="pending-action">'+(processing?'<span class="badge">PROCESSING OCR</span>':'<button class="primary" onclick="verifyJob('+x.id+')">Review</button>')+'</div></div>'
  }).join("")+'</div>';
}

function testRow(t={},i=0){return '<div class="test-card"><div class="test-title"><span>Test result '+(i+1)+'</span><button type="button" class="remove-test danger" onclick="this.parentElement.parentElement.remove()">Remove</button></div><div class="test-fields"><div class="field"><label>SECTION</label><input data-k="section" placeholder="e.g. Physical Examination" value="'+esc(t.section||"Examination Results")+'"></div><div class="field"><label>PROPERTY / TEST</label><input data-k="name" placeholder="OCR-extracted test name" value="'+esc(t.name)+'"></div><div class="field"><label>RESULT / VALUE</label><input data-k="value" placeholder="OCR-extracted result" value="'+esc(t.value)+'"></div><div class="field"><label>UNIT</label><input data-k="unit" placeholder="Unit (if present)" value="'+esc(t.unit)+'"></div><div class="field"><label>REFERENCE RANGE</label><input data-k="reference_range" placeholder="e.g. 40-60" value="'+esc(t.reference_range||"")+'"></div></div></div>'}
function verify(id,d){
  currentPage="capture";
  const p=d.patient||{},tests=d.tests||[],meta=d.report||{};
  app.innerHTML=shell('<div class="wrap"><div class="page-head"><div><div class="eyebrow">Technician review</div><h1>Verify report #'+id+'</h1><p>Confirm the OCR result before generating the centre PDF.</p></div><span class="badge">DRAFT · REVIEW REQUIRED</span></div><div class="card verify-card"><div class="verify-banner"><div><b>Review carefully</b><div class="muted">OCR is draft data. Edit patient credentials, report headings and every test value before approval.</div></div><span class="eyebrow">Report '+id+'</span></div><h3>Patient information</h3><div class="grid" style="grid-template-columns:repeat(4,minmax(0,1fr))">'+[['name','Patient name'],['age','Age'],['sex','Sex'],['phone','WhatsApp number'],['code','Patient ID'],['uhid','UHID'],['referred_by','Referred by'],['received_on','Received on'],['reported_on','Reported on']].map(a=>'<div class="field"><label>'+a[1].toUpperCase()+'</label><input id="v_'+a[0]+'" value="'+esc(p[a[0]]||"")+'"></div>').join("")+'</div><h3 style="margin-top:22px">Report heading</h3><div class="grid" style="grid-template-columns:repeat(2,minmax(0,1fr))"><div class="field"><label>DEPARTMENT</label><input id="v_department" value="'+esc(meta.department||"")+'" placeholder="e.g. Department of Clinical Pathology"></div><div class="field"><label>REPORT TITLE</label><input id="v_title" value="'+esc(meta.title||"")+'" placeholder="e.g. Report on Examination of Stool"></div></div><h3>Extracted test results</h3><p class="muted">Group each result into a section so the final PDF reads like a professional laboratory report.</p><div id="tests">'+(tests.length?tests.map((t,i)=>testRow(t,i)).join(""):'<div class="empty-tests">No test results were extracted. Add a result below if it is visible on the report.</div>')+'</div><div class="actions"><button type="button" onclick="addTest()">＋ Add test result</button><button type="button" class="danger" onclick="deleteVerification('+id+')">Delete report</button><button class="primary" onclick="approve('+id+')">Approve & generate PDF</button></div></div></div>')
}
async function deleteVerification(id){
  const ok=window.confirm("Delete report #"+id+"? This will permanently remove the uploaded slip and its OCR draft. This action cannot be undone.");
  if(!ok)return;
  try{
    await api("/api/reports/"+id,{method:"DELETE"});
    alert("Report #"+id+" was deleted.");
    await pending();
  }catch(e){alert(e.message)}
}
function addTest(){const el=document.getElementById("tests");const n=el.querySelectorAll(".test-card").length;const empty=el.querySelector(".empty-tests");if(empty)empty.remove();el.insertAdjacentHTML("beforeend",testRow({},n))}
async function approve(id){
  const field=k=>document.getElementById("v_"+k)?.value||"";
  const d={patient:{name:field("name"),age:field("age"),sex:field("sex"),phone:field("phone"),code:field("code"),uhid:field("uhid"),referred_by:field("referred_by"),received_on:field("received_on"),reported_on:field("reported_on")},report:{department:field("department"),title:field("title")},tests:[...document.querySelectorAll(".test-card")].map(x=>Object.fromEntries([...x.querySelectorAll("[data-k]")].map(i=>[i.dataset.k,i.value])))};
  const f=new FormData();f.append("data",JSON.stringify(d));
  try{await api("/api/reports/"+id+"/verify",{method:"POST",body:f});await pay(id)}catch(e){alert(e.message)}
}
async function pay(id){const s=await api("/api/settings");currentPage="reports";app.innerHTML=shell('<div class="wrap"><div class="page-head"><div><div class="eyebrow">Report finalized</div><h1>Report #'+id+'</h1><p>The generated PDF is ready for the centre.</p></div><span class="badge status-green">PDF READY</span></div><div class="card"><div class="actions"><button class="primary" onclick="downloadPDF('+id+')">↓ Download generated PDF</button><button onclick="reports()">Back to reports</button></div><hr><h3>Patient delivery</h3>'+(s.whatsapp_enabled?'<p class="muted">WhatsApp automation is enabled. Choose the payment state for this report.</p><div class="settings-grid"><div class="field"><label>PATIENT CHARGE ₹</label><input id="amt" type="number" min="0" step=".01"></div><div class="field"><label>PAYMENT STATE</label><select id="ps"><option value="PAID">Paid</option><option value="DUE">Due / Pending</option></select></div></div><button class="primary" onclick="savePay('+id+')">Save payment & queue delivery</button>':'<div class="notice"><b>WhatsApp is OFF.</b><br><span class="muted">No patient message will be sent.</span></div>')+'</div></div>')}
async function savePay(id){try{await api("/api/payments/"+id,{method:"POST",body:new URLSearchParams({amount:document.getElementById("amt")?.value||0,status:document.getElementById("ps")?.value||"PAID"})});alert("Payment state saved. Automation queued.");await reports()}catch(e){alert(e.message)}}
async function reports(){currentPage="reports";const r=await api("/api/reports");app.innerHTML=shell('<div class="wrap"><div class="page-head"><div><div class="eyebrow">Records</div><h1>Reports</h1><p>Search and download reports from this centre.</p></div><button class="primary" onclick="capture()">＋ New report</button></div><div class="card"><div class="searchbar"><input id="search" placeholder="Search patient, ID or WhatsApp" oninput="filterReports()"><button onclick="reports()">Refresh</button></div><div id="reportlist" class="table-wrap">'+rows(r)+'</div></div></div>')}
async function filterReports(){const r=await api("/api/reports?search="+encodeURIComponent(document.getElementById("search").value));document.getElementById("reportlist").innerHTML=rows(r)}
function rows(r){return r.length?'<table class="table"><thead><tr><th>Report</th><th>Patient</th><th>Status</th><th>Payment</th><th>PDF</th></tr></thead><tbody>'+r.map(x=>'<tr><td><b>#'+x.id+'</b></td><td>'+esc(x.patient_name||"—")+'</td><td><span class="badge '+(x.status==="GENERATED"||x.status==="VERIFIED"?"status-green":"")+'">'+esc(x.status)+'</span></td><td>'+esc(x.payment||"—")+'</td><td>'+(x.pdf_path?'<button onclick="downloadPDF('+x.id+')">Download</button>':'<span class="muted">Not ready</span>')+'</td></tr>').join("")+'</tbody></table>':'<p class="muted">No reports found.</p>'}
async function notes(){currentPage="notes";const n=await api("/api/notifications");app.innerHTML=shell('<div class="wrap"><div class="page-head"><div><div class="eyebrow">Activity</div><h1>Notifications</h1><p>Patient report delivery and centre events.</p></div></div><div class="card">'+(n.length?n.map(x=>'<div class="notice"><b>'+esc(x.kind)+'</b><p>'+esc(x.message)+'</p><small class="muted">'+esc(x.created_at)+'</small></div>').join(""):'<p class="muted">No notifications yet.</p>')+'</div></div>')}
async function settings(){currentPage="settings";const s=await api("/api/settings");app.innerHTML=shell('<div class="wrap"><div class="page-head"><div><div class="eyebrow">Administration</div><h1>Centre settings</h1><p>Configure patient delivery and your report template.</p></div></div><div class="settings-grid"><div class="card"><h3>Patient delivery</h3><div class="field"><label>WHATSAPP AUTOMATION</label><select id="wa"><option value="false">OFF</option><option value="true" '+(s.whatsapp_enabled?"selected":"")+'>ON</option></select></div><div class="field"><label>CENTRE UPI ID</label><input id="upi" value="'+esc(s.upi_id)+'" placeholder="centre@upi"></div><div class="notice"><b>Automatic delivery</b><br><span class="muted">Due → payment request. Paid/verified → final report delivery.</span></div><div class="notice"><b>Provider:</b> '+esc(s.whatsapp_provider||"mock")+'<br><b>Payment template:</b> '+esc(s.payment_template||"—")+'<br><b>Report template:</b> '+esc(s.report_template||"—")+'</div><div class="notice">Credits available: <b>'+esc(s.credits)+'</b><br>Current credit price: <b>₹'+esc(s.credit_price_inr)+'</b></div><button class="primary" onclick="saveSettings()">Save delivery settings</button></div><div class="card"><h3>Report template</h3><p class="muted">Upload the blank PDF used by your centre. Aarogyam places generated report content into the template body.</p><input id="tpl" type="file" accept=".pdf,image/png,image/jpeg,image/webp"><br><br><button onclick="uploadTemplate()">Upload PDF template</button><div class="footer-note">Template placement should be validated against your actual centre letterhead before production.</div><hr><h3>Report design</h3><p class="muted">Choose which patient fields and result columns appear, plus the basic visual style. This is saved separately for this centre and applied to future PDFs.</p><button class="primary" onclick="reportDesigner()">Open Report Designer</button></div></div></div>')}

async function reportDesigner(){
  currentPage="settings";
  const s=await api("/api/settings");
  const l=s.report_layout||{}, p=l.patient||{}, r=l.results||{}, a=l.appearance||{}, pg=l.page||{}, body=l.body||{}, manual=l.manual||{};
  const pv=(k,d)=>p[k]===undefined?d:p[k], rv=(k,d)=>r[k]===undefined?d:r[k], av=(k,d)=>a[k]===undefined?d:a[k], gv=(k,d)=>pg[k]===undefined?d:pg[k];
  const visible=p.visible||["name","age","sex","code","uhid","referred_by","received_on","reported_on","phone"];
  const order=p.order||["name","age_gender","code","uhid","referred_by","received_on","reported_on","phone"];
  const cols=r.columns||["name","value","unit","reference_range"];
  const fields=[["name","Patient Name"],["age","Age"],["sex","Gender"],["code","Patient ID"],["uhid","UHID"],["referred_by","Referred By"],["received_on","Received On"],["reported_on","Reported On"],["phone","Phone"]];
  const resultDefs=[["name","Parameter"],["value","Result"],["unit","Unit"],["reference_range","Reference Range"]];
  const mode=l.mode||l.template_mode||((s.report_template&&s.report_template!=="—")?"template":"manual");
  app.innerHTML=shell(`
  <div class="wrap template-designer">
    <div class="page-head">
      <div><div class="eyebrow">Master template</div><h1>Report Template Designer</h1><p>Design once. Every future patient report uses this layout automatically.</p></div>
      <div class="actions"><button onclick="settings()">Back</button><button class="primary" onclick="saveReportLayout()">Save master template</button></div>
    </div>

    <div class="designer-modebar card">
      <div><div><b>How should the page be built?</b><span class="muted">Choose the master page source. Test names and results are never configured here.</span></div></div>
      <div class="designer-mode-switch">
        <button type="button" class="${mode==="template"?"active":""}" data-mode="template" onclick="setDesignerMode('template')"><strong>Letterhead template</strong><small>Use uploaded PDF/image as the page background</small></button>
        <button type="button" class="${mode==="manual"?"active":""}" data-mode="manual" onclick="setDesignerMode('manual')"><strong>Manual builder</strong><small>Build the page from Aarogyam blocks</small></button>
      </div>
      <input id="designerMode" type="hidden" value="${mode}">
    </div>

    <div class="designer-workbench">
      <aside class="designer-inspector">
        <div class="inspector-title"><span class="eyebrow">Template blocks</span><b>Master layout</b></div>

        <section class="inspector-card">
          <div class="inspector-head"><span>01</span><div><b>Page & body</b><small>Paper size and safe report area</small></div></div>
          <div class="settings-grid">
            <div class="field"><label>PAGE</label><select id="layoutPageSize" onchange="updateDesignerPreview()"><option value="A4" ${gv("size","A4")==="A4"?"selected":""}>A4</option><option value="A5" ${gv("size","A4")==="A5"?"selected":""}>A5</option><option value="LETTER" ${gv("size","A4")==="LETTER"?"selected":""}>Letter</option><option value="LEGAL" ${gv("size","A4")==="LEGAL"?"selected":""}>Legal</option></select></div>
            <div class="field"><label>TOP</label><input id="layoutTop" type="number" value="${esc(gv("top",132))}" oninput="updateDesignerPreview()"></div>
            <div class="field"><label>BOTTOM</label><input id="layoutBottom" type="number" value="${esc(gv("bottom",82))}" oninput="updateDesignerPreview()"></div>
            <div class="field"><label>LEFT</label><input id="layoutLeft" type="number" value="${esc(gv("left",52))}" oninput="updateDesignerPreview()"></div>
            <div class="field"><label>RIGHT</label><input id="layoutRight" type="number" value="${esc(gv("right",52))}" oninput="updateDesignerPreview()"></div>
          </div>
          <div class="inspector-actions">
            <input id="tplDesigner" type="file" accept=".pdf,image/png,image/jpeg,image/webp" hidden onchange="uploadTemplateFromDesigner(this)">
            <button type="button" onclick="document.getElementById('tplDesigner').click()">Upload / replace letterhead</button>
            <button type="button" onclick="clearTemplatePreview()">Remove letterhead</button>
          </div>
        </section>

        <section class="inspector-card">
          <div class="inspector-head"><span>02</span><div><b>Patient block</b><small>Credentials are filled from each report</small></div></div>
          <div class="designer-check-grid">${fields.map(x=>`<label class="check-row"><input type="checkbox" class="patient-field" value="${x[0]}" ${visible.includes(x[0])?"checked":""} onchange="updateDesignerPreview()"><span>${x[1]}</span></label>`).join("")}</div>
          <div class="settings-grid">
            <div class="field"><label>COLUMNS</label><select id="layoutPatientColumns" onchange="updateDesignerPreview()"><option value="1" ${Number(pv("columns",2))===1?"selected":""}>1</option><option value="2" ${Number(pv("columns",2))===2?"selected":""}>2</option></select></div>
            <div class="field"><label>STYLE</label><select id="layoutPatientStyle" onchange="updateDesignerPreview()"><option value="card" ${pv("style","card")==="card"?"selected":""}>Card</option><option value="plain" ${pv("style","card")==="plain"?"selected":""}>Plain</option></select></div>
            <div class="field"><label>BACKGROUND</label><input id="layoutPatientBg" type="color" value="${esc(pv("background","#F5F6F8"))}" oninput="updateDesignerPreview()"></div>
            <div class="field"><label>TEXT SIZE</label><input id="layoutPatientSize" type="number" step=".5" value="${esc(pv("font_size",8.5))}" oninput="updateDesignerPreview()"></div>
          </div>
          <div class="field"><label>ORDER</label><input id="layoutPatientOrder" value="${esc(order.join(", "))}" oninput="updateDesignerPreview()"></div>
        </section>

        <section class="inspector-card">
          <div class="inspector-head"><span>03</span><div><b>Dynamic report body</b><small>One loop handles every test type</small></div></div>
          <div class="dynamic-rule"><b>↻ Dynamic section loop</b><span>At PDF generation time Aarogyam reads the verified report and creates as many sections and rows as needed.</span></div>
          <div class="settings-grid">
            <div class="field"><label>FONT</label><select id="layoutFont" onchange="updateDesignerPreview()"><option value="Helvetica" ${av("font","Helvetica")==="Helvetica"?"selected":""}>Helvetica</option><option value="Times-Roman" ${av("font","Helvetica")==="Times-Roman"?"selected":""}>Times</option><option value="Courier" ${av("font","Helvetica")==="Courier"?"selected":""}>Courier</option></select></div>
            <div class="field"><label>SECTION ALIGN</label><select id="layoutSectionAlign" onchange="updateDesignerPreview()"><option value="left" ${rv("section_align","left")==="left"?"selected":""}>Left</option><option value="center" ${rv("section_align","left")==="center"?"selected":""}>Center</option><option value="right" ${rv("section_align","left")==="right"?"selected":""}>Right</option></select></div>
            <div class="field"><label>SECTION SIZE</label><input id="layoutSectionSize" type="number" step=".5" value="${esc(rv("section_font_size",7.9))}" oninput="updateDesignerPreview()"></div>
            <div class="field"><label>RESULT SIZE</label><input id="layoutResultSize" type="number" step=".5" value="${esc(rv("font_size",9))}" oninput="updateDesignerPreview()"></div>
            <div class="field"><label>SECTION BG</label><input id="layoutSectionBg" type="color" value="${esc(rv("section_background","#EEF3F8"))}" oninput="updateDesignerPreview()"></div>
            <div class="field"><label>TABLE HEADER</label><input id="layoutTableBg" type="color" value="${esc(rv("table_header_background","#F7F7FA"))}" oninput="updateDesignerPreview()"></div>
          </div>
          <div class="designer-check-grid">${resultDefs.map(x=>`<label class="check-row"><input type="checkbox" class="result-column" value="${x[0]}" ${cols.includes(x[0])?"checked":""} onchange="updateDesignerPreview()"><span>${x[1]}</span></label>`).join("")}</div>
          <div class="designer-check-grid compact-checks">
            <label class="check-row"><input id="layoutSectionHeaders" type="checkbox" ${rv("section_headers",true)?"checked":""} onchange="updateDesignerPreview()"><span>Show section headings</span></label>
            <label class="check-row"><input id="layoutSectionBold" type="checkbox" ${rv("section_bold",true)?"checked":""} onchange="updateDesignerPreview()"><span>Bold section headings</span></label>
            <label class="check-row"><input id="layoutGrid" type="checkbox" ${rv("show_grid",false)?"checked":""} onchange="updateDesignerPreview()"><span>Show table grid</span></label>
          </div>
        </section>

        <section class="inspector-card">
          <div class="inspector-head"><span>04</span><div><b>Header & identity</b><small>Manual mode only</small></div></div>
          <div class="inspector-actions">
            <input id="logoDesigner" type="file" accept="image/png,image/jpeg,image/webp" hidden onchange="uploadCentreLogo(this)">
            <button type="button" onclick="document.getElementById('logoDesigner').click()">Add / replace centre logo</button>
          </div>
          <div class="field"><label>HEADER TEXT</label><textarea id="manualHeaderText" rows="2" oninput="updateDesignerPreview()">${esc(manual.header_text||"Centre name • Address • Contact")}</textarea></div>
        </section>

        <section class="inspector-card">
          <div class="inspector-head"><span>05</span><div><b>Footer & signature</b><small>Manual mode only</small></div></div>
          <div class="field"><label>FOOTER TEXT</label><textarea id="manualFooterText" rows="2" oninput="updateDesignerPreview()">${esc(manual.footer_text||"Doctor / Authorised Signatory • Centre contact")}</textarea></div>
          <div class="field"><label>TEXT COLOUR</label><input id="manualTextColour" type="color" value="${esc(manual.text_color||"#52606D")}" oninput="updateDesignerPreview()"></div>
        </section>

        <div class="designer-tip"><b>Important</b><span>No LFT, CBC, thyroid, urine or other test is stored in this template. Those names, rows, results, units and reference ranges come only from the patient's verified report.</span></div>
      </aside>

      <main class="designer-stage">
        <div class="stage-toolbar"><div><span class="eyebrow">Canvas</span><b id="designerPreviewTitle">Master report page</b></div><span class="canvas-badge">LIVE</span></div>
        <div id="reportPreviewViewport" class="report-preview-viewport">
          <div id="reportPreviewPage" class="visual-report-page master-canvas">
            <div id="previewLetterhead" class="preview-letterhead"><span>LETTERHEAD / STATIC BACKGROUND</span></div>
            <div class="master-block preview-manual-header" data-block="header"><span id="previewHeaderText"></span></div>
            <div class="master-block preview-patient-block" data-block="patient">
              <div class="block-tag">PATIENT CREDENTIALS</div>
              <div id="previewPatientFields"></div>
            </div>
            <div class="master-block preview-body-block" data-block="body">
              <div class="block-tag">DYNAMIC REPORT BODY</div>
              <div class="body-placeholder"><b>[TEST SECTION NAME]</b><div>[PARAMETER] <strong>[RESULT]</strong> [UNIT] <em>[REFERENCE RANGE]</em></div><div>[MORE PARAMETERS…]</div></div>
            </div>
            <div class="master-block preview-footer-block" data-block="footer"><span id="previewFooterText"></span><span class="signature-placeholder">Authorised Signatory</span></div>
          </div>
        </div>
        <div class="canvas-note"><b>Live master preview</b><span>Placeholders show the structure only. A real report replaces them with its own patient details, test sections, parameters, results, units and reference ranges. Long reports continue onto additional PDF pages.</span></div>
      </main>
    </div>
  </div>`);
  await refreshCentreLogoPreview();
  updateDesignerPreview();
}

function setDesignerMode(mode){
  const el=document.getElementById("designerMode");if(el)el.value=mode;
  document.querySelectorAll(".designer-mode-switch button").forEach(b=>b.classList.toggle("active",b.dataset.mode===mode));
  const letter=document.getElementById("previewLetterhead"), manual=document.querySelector(".preview-manual-header");
  if(letter)letter.style.display=mode==="template"?"flex":"none";
  if(manual)manual.style.display=mode==="manual"?"block":"none";
  updateDesignerPreview();
}

function updateDesignerPreview(){
  const mode=document.getElementById("designerMode")?.value||"manual";
  const page=document.getElementById("reportPreviewPage");
  if(!page)return;
  setDesignerModeVisual(mode);
  const patientWrap=document.getElementById("previewPatientFields");
  const checked=Array.from(document.querySelectorAll(".patient-field")).filter(x=>x.checked).map(x=>x.value);
  const labels={name:"Patient Name",age:"Age",sex:"Gender",code:"Patient ID",uhid:"UHID",referred_by:"Referred By",received_on:"Received On",reported_on:"Reported On",phone:"Phone"};
  const order=(document.getElementById("layoutPatientOrder")?.value||"").split(",").map(x=>x.trim()).filter(Boolean);
  const fields=(order.length?order:checked).filter(x=>checked.includes(x));
  if(patientWrap){
    patientWrap.style.gridTemplateColumns=Number(document.getElementById("layoutPatientColumns")?.value||2)===1?"1fr":"1fr 1fr";
    patientWrap.innerHTML=fields.map(k=>`<span><small>${esc(labels[k]||k)}</small><b>[${esc((labels[k]||k).toUpperCase())}]</b></span>`).join("");
  }
  const sectionBg=document.getElementById("layoutSectionBg")?.value||"#EEF3F8";
  const tableBg=document.getElementById("layoutTableBg")?.value||"#F7F7FA";
  const sectionAlign=document.getElementById("layoutSectionAlign")?.value||"left";
  const sectionHeaders=document.getElementById("layoutSectionHeaders")?.checked!==false;
  const header=document.getElementById("previewHeaderText"),footer=document.getElementById("previewFooterText");
  if(header)header.textContent=document.getElementById("manualHeaderText")?.value||"Centre name • Address • Contact";
  if(footer)footer.textContent=document.getElementById("manualFooterText")?.value||"Doctor / Authorised Signatory • Centre contact";
  const body=document.querySelector(".preview-body-block");
  if(body){
    body.querySelector(".block-tag").style.display=sectionHeaders?"block":"none";
    body.querySelector(".body-placeholder").style.background=tableBg;
    body.querySelector(".body-placeholder").style.borderColor=sectionBg;
    body.querySelector(".body-placeholder").style.textAlign=sectionAlign;
  }
  page.dataset.pageSize=document.getElementById("layoutPageSize")?.value||"A4";
  requestReportPreviewScale();
}

function setDesignerModeVisual(mode){
  const letter=document.getElementById("previewLetterhead"), manual=document.querySelector(".preview-manual-header");
  if(letter)letter.style.display=mode==="template"?"flex":"none";
  if(manual)manual.style.display=mode==="manual"?"block":"none";
}

let reportPreviewScaleFrame=0;
function requestReportPreviewScale(){
  cancelAnimationFrame(reportPreviewScaleFrame);
  reportPreviewScaleFrame=requestAnimationFrame(()=>requestAnimationFrame(scaleReportPreview));
}
function scaleReportPreview(){
  const viewport=document.getElementById("reportPreviewViewport"),page=document.getElementById("reportPreviewPage");
  if(!viewport||!page)return;
  const pageWidth=page.offsetWidth,pageHeight=page.offsetHeight;
  if(!pageWidth||!pageHeight)return;
  const styles=getComputedStyle(viewport);
  const availableWidth=Math.max(1,viewport.clientWidth-parseFloat(styles.paddingLeft||"0")-parseFloat(styles.paddingRight||"0"));
  const scale=Math.min(1,availableWidth/pageWidth);
  page.style.transformOrigin="top left";
  page.style.transform="scale("+scale+")";
  viewport.style.height=Math.ceil(pageHeight*scale+parseFloat(styles.paddingTop||"0")+parseFloat(styles.paddingBottom||"0"))+"px";
  viewport.style.overflowX="hidden";
  page.style.marginLeft=Math.max(0,(availableWidth-pageWidth*scale)/2)+"px";
}
function initReportPreviewScaling(){requestReportPreviewScale();setTimeout(requestReportPreviewScale,0);setTimeout(requestReportPreviewScale,100);setTimeout(requestReportPreviewScale,300)}
window.addEventListener("resize",requestReportPreviewScale);
window.addEventListener("orientationchange",()=>setTimeout(requestReportPreviewScale,50));

async function uploadCentreLogo(input){
  if(!input.files[0])return;
  const f=new FormData();f.append("file",input.files[0]);
  try{
    await api("/api/settings/logo",{method:"POST",body:f});
    await refreshCentreLogoPreview();
    alert("Centre logo saved.");
  }catch(e){alert(e.message)}
}

async function refreshCentreLogoPreview(){
  const overlay=document.getElementById("previewOverlay");if(!overlay)return;
  try{
    const res=await fetch("/api/settings/logo",{headers:{Authorization:"Bearer "+token}});
    if(!res.ok)return;
    const blob=await res.blob();
    if(window._aarogyamLogoUrl)URL.revokeObjectURL(window._aarogyamLogoUrl);
    window._aarogyamLogoUrl=URL.createObjectURL(blob);
    let img=document.getElementById("previewCentreLogo");
    if(!img){
      img=document.createElement("img");img.id="previewCentreLogo";img.className="preview-centre-logo";
      img.draggable=true;img.title="Drag logo in preview";
      overlay.appendChild(img);
    }
    img.src=window._aarogyamLogoUrl;
  }catch(e){}
}

async function refreshReportTemplatePreview(){
  const frame=document.getElementById("templateFrame"); if(!frame)return;
  try{
    const res=await fetch("/api/settings/template",{headers:{Authorization:"Bearer "+token}});
    if(!res.ok){frame.src="about:blank";return}
    const blob=await res.blob();
    if(window._aarogyamTemplateUrl)URL.revokeObjectURL(window._aarogyamTemplateUrl);
    window._aarogyamTemplateUrl=URL.createObjectURL(blob);
    frame.src=window._aarogyamTemplateUrl;
  }catch(e){frame.src="about:blank"}
}

async function uploadTemplateFromDesigner(input){
  if(!input.files[0])return;
  const f=new FormData();f.append("file",input.files[0]);
  try{
    await api("/api/settings/template",{method:"POST",body:f});
    alert("Letterhead template saved. Future reports will use it as the static page background.");
  }catch(e){alert(e.message)}
}

async function clearTemplatePreview(){
  try{
    await api("/api/settings/template",{method:"DELETE"});
    alert("Manual builder mode enabled. Future reports will use the saved designer header/footer instead of an uploaded template.");
  }catch(e){alert(e.message)}
}


async function applyReportPreset(key){
  const presets={clinical:{patientBg:"#F6F8FB",sectionBg:"#EEF3F8",tableBg:"#F8FAFC",text:"#172033",accent:"#285F8F",font:"Helvetica",patientStyle:"card"},modern:{patientBg:"#F6F7FC",sectionBg:"#F0EEFF",tableBg:"#FAFAFD",text:"#151A2D",accent:"#5F52E8",font:"Helvetica",patientStyle:"card"},minimal:{patientBg:"#FFFFFF",sectionBg:"#F5F6F8",tableBg:"#FBFBFC",text:"#20242D",accent:"#52606D",font:"Helvetica",patientStyle:"plain"}};
  const p=presets[key];if(!p)return;
  const set=(id,v)=>{const e=document.getElementById(id);if(e)e.value=v};
  set("layoutPatientBg",p.patientBg);set("layoutSectionBg",p.sectionBg);set("layoutTableBg",p.tableBg);set("layoutSectionText",p.text);set("layoutFont",p.font);set("layoutPatientStyle",p.patientStyle);set("layoutSectionAlign","left");
  updateDesignerPreview();
}

async function saveReportLayout(){
  const current=await api("/api/settings");
  const checked=s=>Array.from(document.querySelectorAll(s)).filter(x=>x.checked).map(x=>x.value);
  const visible=checked(".patient-field"), columns=checked(".result-column");
  if(!visible.includes("name"))visible.unshift("name");
  if(!columns.includes("name"))columns.unshift("name");
  const order=(document.getElementById("layoutPatientOrder")?.value||"").split(",").map(x=>x.trim()).filter(Boolean);
  const mode=document.getElementById("designerMode")?.value||"manual";
  const layout={
    mode,
    template_mode:mode,
    page:{size:document.getElementById("layoutPageSize").value,left:Number(document.getElementById("layoutLeft").value),right:Number(document.getElementById("layoutRight").value),top:Number(document.getElementById("layoutTop").value),bottom:Number(document.getElementById("layoutBottom").value)},
    patient:{visible,order,columns:Number(document.getElementById("layoutPatientColumns").value),style:document.getElementById("layoutPatientStyle").value,font_size:Number(document.getElementById("layoutPatientSize").value),label_bold:true,background:document.getElementById("layoutPatientBg").value,border:"#E1E5EC"},
    body:{dynamic:true,source:"verified_report",loop:"sections_then_rows",multi_page:true},
    results:{columns,section_order:[],section_headers:document.getElementById("layoutSectionHeaders").checked,section_align:document.getElementById("layoutSectionAlign").value,section_bold:document.getElementById("layoutSectionBold").checked,section_font_size:Number(document.getElementById("layoutSectionSize").value),section_text:"#151A2D",section_background:document.getElementById("layoutSectionBg").value,section_padding:5,table_header_background:document.getElementById("layoutTableBg").value,row_alt_background:"#FBFCFE",font_size:Number(document.getElementById("layoutResultSize").value),header_size:7.2,show_grid:document.getElementById("layoutGrid").checked},
    appearance:{text:"#151A2D",accent:"#5F52E8",muted:"#667085",font:document.getElementById("layoutFont").value},
    manual:{header_text:document.getElementById("manualHeaderText").value,footer_text:document.getElementById("manualFooterText").value,text_color:document.getElementById("manualTextColour").value}
  };
  try{
    await api("/api/settings",{method:"PUT",body:new URLSearchParams({whatsapp_enabled:""+current.whatsapp_enabled,upi_id:current.upi_id||"",report_layout:JSON.stringify(layout)})});
    alert("Master template saved. Future PDFs will use this layout.");
  }catch(e){alert(e.message)}
}

async function saveSettings(){try{await api("/api/settings",{method:"PUT",body:new URLSearchParams({whatsapp_enabled:document.getElementById("wa").value,upi_id:document.getElementById("upi").value})});alert("Settings saved");await settings()}catch(e){alert(e.message)}}
async function uploadTemplate(){const el=document.getElementById("tpl");if(!el.files[0])return alert("Choose a PDF or image template");const f=new FormData();f.append("file",el.files[0]);try{await api("/api/settings/template",{method:"POST",body:f});alert("Template saved. Future generated reports will use it as the static letterhead.");await settings()}catch(e){alert(e.message)}}
window.addEventListener("error",e=>{showError(e.error||e.message||"Aarogyam could not start")});
window.addEventListener("unhandledrejection",e=>{showError(e.reason||"Unexpected error")});
function startAarogyam(){try{if(!app)throw Error("Application shell not found");boot().catch(showError)}catch(e){showError(e)}}
startAarogyam();
setTimeout(()=>{if(app&&app.innerText.includes("Loading workspace"))showError("The workspace did not start. The browser did not complete application startup. Please refresh once.")},5000);