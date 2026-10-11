// Reservation View is informational only; live Check-out, Transfer Room, and Early/Late operations remain in the Occupied Rooms Action menu.
const DASHBOARD_CONFIG = window.YH_DASHBOARD_CONFIG || {apiBase:"/api/v1", requestTimeoutMs:15000};
const API = DASHBOARD_CONFIG.apiBase.replace(/\/$/,"");
const SESSION = window.sessionStorage;
const state = { token: SESSION.getItem("yh_access_token") || "", user: null, hotelContext: null, page: "dashboard", data: null, listPages: {}, restaurantSection: "overview", kitchenSummaryOpen: "" };

const NAV = [
  {section:"Overview",items:[
    ["dashboard","▦","Dashboard"],["frontdesk","◉","Front Desk"],["hotel","⌂","Hotel Information"],["mapsmedia","⌖","Maps & Media"]
  ]},
  {section:"Operations",items:[
    ["guests","♙","Guests"],["rooms","▣","Rooms & Reservations"],["restaurant","◌","Restaurant / POS"],["billing","₹","Billing & Payments"],
    ["inventory","▤","Inventory"],["procurement","▧","Suppliers & Procurement"],["transport","⇄","Transportation"]
  ]},
  {section:"People & Experience",items:[
    ["hr","♟","Staff & HR"],["expenses","₹","Expenses"],["feedback","★","Feedback"],["notifications","◔","Notifications"]
  ]},
  {section:"Intelligence",items:[
    ["reports","▥","Reports & Analytics"],["audit","≡","Audit & Activity"],["admin","⚙","Administration"]
  ]}
];

const GETS = {
  guests:"/customers", rooms:"/room-bookings", roomlist:"/rooms", restaurant:"/restaurant/orders", menu:"/restaurant/menu",
  tables:"/tables", billing:"/billing/invoices", expenses:"/expenses", inventory:"/inventory/items", lowstock:"/inventory/low-stock",
  valuation:"/inventory/valuation", suppliers:"/suppliers", purchaseorders:"/procurement/purchase-orders", receivings:"/procurement/receivings",
  staff:"/staff", departments:"/departments", attendance:"/attendance", leave:"/leave", salary:"/salary", payroll:"/payroll",
  feedback:"/feedback", notifications:"/notifications", channels:"/notifications/channels", transportation:"/transportation/requests",
  vehicles:"/transportation/vehicles", drivers:"/transportation/drivers", audit:"/admin/audit", users:"/admin/users", roles:"/admin/roles",
  permissions:"/admin/permissions"
};

function esc(v){return String(v??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[c]));}
function money(v){const n=Number(v||0);return "₹"+n.toLocaleString("en-IN",{maximumFractionDigits:2});}
function dateNow(){const d=new Date();const pad=n=>String(n).padStart(2,"0");return `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())}`;}
function istDateTime(value){
  const text=String(value??"").trim();
  if(!text)return "—";
  // SQLite CURRENT_TIMESTAMP values are UTC. Display them in India Standard Time.
  const hasTimezone=/([zZ]|[+-]\d{2}:?\d{2})$/.test(text);
  let date;
  if(hasTimezone){
    date=new Date(text);
  }else if(/^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?$/.test(text)){
    date=new Date(text.replace(" ","T")+"Z");
  }else{
    return text;
  }
  if(Number.isNaN(date.getTime()))return text;
  return new Intl.DateTimeFormat("en-IN",{
    timeZone:"Asia/Kolkata",day:"2-digit",month:"2-digit",year:"numeric",
    hour:"2-digit",minute:"2-digit",second:"2-digit",hour12:true
  }).format(date).replace(",", "");
}
function parseRestaurantOrderDate(value){
  const text=String(value||"").trim();
  if(!text)return null;
  const iso=text.match(/^(\\d{4})-(\\d{2})-(\\d{2})/);
  if(iso)return `${iso[1]}-${iso[2]}-${iso[3]}`;
  const ddmmyyyy=text.match(/^(\\d{2})[-\\/](\\d{2})[-\\/](\\d{4})/);
  if(ddmmyyyy)return `${ddmmyyyy[3]}-${ddmmyyyy[2]}-${ddmmyyyy[1]}`;
  return null;
}
function addRestaurantOrderDays(iso,days){
  const d=new Date(`${iso}T00:00:00`);
  d.setDate(d.getDate()+days);
  return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,"0")}-${String(d.getDate()).padStart(2,"0")}`;
}
function toast(msg,error=false){const el=document.createElement("div");el.className="toast"+(error?" error":"");el.textContent=msg;document.getElementById("toast-region").appendChild(el);setTimeout(()=>el.remove(),3200);}
async function api(path,opts={}){
  const headers={"Content-Type":"application/json",...(opts.headers||{})};
  if(state.token) headers.Authorization=`Bearer ${state.token}`;
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), DASHBOARD_CONFIG.requestTimeoutMs);
  let res;
  try {
    res=await fetch(API+path,{...opts,headers,signal:controller.signal});
  } catch (err) {
    if (err && err.name === "AbortError") throw new Error("Request timed out. Please try again.");
    throw new Error("Network error. Please check the server connection.");
  } finally {
    clearTimeout(timeout);
  }
  if(res.status===401){state.token="";state.user=null;SESSION.removeItem("yh_access_token");showLogin("Session expired. Please sign in again.");throw new Error("Authentication required.");}
  const text=await res.text(); let body={}; try{body=text?JSON.parse(text):{}}catch{body={detail:text}};
  if(!res.ok){
    const detail = body.detail;

    const message =
        typeof detail === "string"
            ? detail
            : Array.isArray(detail)
                ? detail.map(x => {
                    if(typeof x === "string") return x;
                    if(x?.msg) return x.msg;
                    return JSON.stringify(x);
                }).join("; ")
                : detail && typeof detail === "object"
                    ? JSON.stringify(detail)
                    : `Request failed (${res.status})`;

    throw new Error(message);
}

return body;
}
let authExpiryTimer = null;
function clearAuthExpiryTimer(){if(authExpiryTimer){clearTimeout(authExpiryTimer);authExpiryTimer=null;}}
function persistAuth(token, user, expiresIn){
  state.token=token; state.user=user;
  const expiresAt=Date.now()+Math.max(0,Number(expiresIn||0))*1000;
  SESSION.setItem("yh_access_token",token);
  SESSION.setItem("yh_token_expires_at",String(expiresAt));
  clearAuthExpiryTimer();
  const remaining=Math.max(0,expiresAt-Date.now()-5000);
  if(remaining>0) authExpiryTimer=setTimeout(()=>forceLogout("Your session has expired. Please sign in again."),remaining);
}
function clearAuth(){clearAuthExpiryTimer();state.token="";state.user=null;state.hotelContext=null;SESSION.removeItem("yh_access_token");SESSION.removeItem("yh_token_expires_at");}
function forceLogout(message=""){clearAuth();showLogin(message);}
function storedTokenIsExpired(){const raw=SESSION.getItem("yh_token_expires_at");return raw && Number(raw)<=Date.now();}
function restoreAuthTimer(){const raw=SESSION.getItem("yh_token_expires_at");if(!raw)return;const remaining=Number(raw)-Date.now()-5000;if(remaining<=0){clearAuth();return;}clearAuthExpiryTimer();authExpiryTimer=setTimeout(()=>forceLogout("Your session has expired. Please sign in again."),remaining);}
function openPasswordChange(){formModal("Change Password",[
 {name:"current_password",label:"Current password",type:"password"},
 {name:"new_password",label:"New password",type:"password",placeholder:"Minimum 8 characters"},
 {name:"confirm_password",label:"Confirm new password",type:"password"}
 ],async o=>{if(o.new_password!==o.confirm_password)throw new Error("New password and confirmation do not match.");await api("/auth/change-password",{method:"POST",body:JSON.stringify({current_password:o.current_password,new_password:o.new_password})});toast("Password changed successfully.");});}
function showLogin(msg=""){const shell=document.getElementById("dashboard-view");shell.classList.remove("kitchen-standalone");document.getElementById("login-view").classList.remove("hidden");shell.classList.add("hidden");document.getElementById("login-error").textContent=msg;}
function showDashboard(){const shell=document.getElementById("dashboard-view");const kitchen=currentRole()==="kitchen";shell.classList.toggle("kitchen-standalone",kitchen);document.getElementById("login-view").classList.add("hidden");shell.classList.remove("hidden");const kitchenLogout=document.getElementById("kitchen-logout-btn");if(kitchenLogout)kitchenLogout.classList.toggle("hidden",!kitchen);}
function normalizePermissionName(value){return String(value??"").trim().toLowerCase().replace(/\s+/g,"_");}
function currentRole(){return normalizePermissionName(state.user?.role??state.user?.role_name??"");}
const ROLE_HOME_PAGE={
  owner:"dashboard",
  manager:"dashboard",
  reception:"frontdesk",
  waiter_service:"restaurant",
  kitchen:"restaurant",
  cleaning:"restaurant",
  housekeeping:"rooms",
  billing_cashier:"billing",
  admin:"dashboard",
  hr:"hr",
  restaurant_staff:"restaurant",
  accountant:"billing"
};
function roleHomePage(){return ROLE_HOME_PAGE[currentRole()]||"dashboard";}
const ROLE_RESTAURANT_SECTIONS={
  owner:["overview","menu","tables","orders","kitchen","bookings"],
  manager:["overview","menu","tables","orders","kitchen","bookings"],
  reception:["overview","tables","orders","bookings"],
  waiter_service:["tables","orders"],
  kitchen:["kitchen"],
  cleaning:["tables"],
  restaurant_staff:["overview","menu","tables","orders","kitchen","bookings"],
  admin:["overview","menu","tables","orders","kitchen","bookings"]
};
const ROLE_ROOM_SECTIONS={
  owner:["overview","rooms","available","future","booked","reservations"],
  manager:["overview","rooms","available","future","booked","reservations"],
  reception:["overview","rooms","available","future","booked","reservations"],
  housekeeping:["overview"]
};
function roleAllowsRestaurantSection(section){
  const allowed=ROLE_RESTAURANT_SECTIONS[currentRole()];
  return !allowed || allowed.includes(section);
}
function roleAllowsRoomSection(section){
  const allowed=ROLE_ROOM_SECTIONS[currentRole()];
  return !allowed || allowed.includes(section);
}
function prepareRoleLanding(){
  const role=currentRole();
  state.page=roleHomePage();
  if(role==="kitchen")state.restaurantSection="kitchen";
  else if(role==="waiter_service")state.restaurantSection="orders";
  else if(role==="cleaning")state.restaurantSection="tables";
  else if(role!=="restaurant_staff")state.restaurantSection="overview";
  if(!roleAllowsRestaurantSection(state.restaurantSection))state.restaurantSection=(ROLE_RESTAURANT_SECTIONS[role]||["overview"])[0];
  if(role==="housekeeping")state.roomSection="overview";
  if(!roleAllowsRoomSection(state.roomSection))state.roomSection=(ROLE_ROOM_SECTIONS[role]||["overview"])[0];
}
function userPermissions(){const raw=state.user?.permissions??[];return Array.isArray(raw)?raw:[];}
function permissionPairs(){return userPermissions().map(p=>({module:normalizePermissionName(p.module_name),action:normalizePermissionName(p.action_name)}));}
function isAdmin(){return ["admin","administrator"].includes(currentRole());}
function hasPermission(moduleName,actionName="View"){if(isAdmin())return true;const moduleKey=normalizePermissionName(moduleName);const actionKey=normalizePermissionName(actionName);if(!moduleKey)return false;return permissionPairs().some(p=>p.module===moduleKey&&p.action===actionKey);}
const NAV_PERMISSION_MAP={
 dashboard:["Reports","View"], frontdesk:["Rooms","View"], hotel:["Hotel","View"], mapsmedia:["Hotel","View"],
 guests:["Customers","View"], rooms:["Rooms","View"], restaurant:["Restaurant","View"], billing:["Rooms","View"],
 inventory:["Inventory","View"], procurement:null, transport:["Hotel","View"], hr:["Staff","View"], expenses:["Expenses","View"],
 feedback:["Customers","View"], notifications:["Reports","View"], reports:["Reports","View"], audit:["Reports","View"], admin:["Users","View"]
};
const ROLE_NAV_ALLOWLIST={
  owner:null,
  manager:null,
  admin:null,
  restaurant_staff:["restaurant"],
  reception:["frontdesk","guests","rooms","restaurant","billing"],
  waiter_service:["restaurant"],
  kitchen:["restaurant"],
  cleaning:["restaurant"],
  housekeeping:["rooms"],
  billing_cashier:["billing"],
  hr:["hr"],
  accountant:["billing"]
};
function canOpenPage(pageId){
  const role=currentRole();
  const allowed=ROLE_NAV_ALLOWLIST[role];
  if(Array.isArray(allowed)&&!allowed.includes(pageId))return false;
  const spec=NAV_PERMISSION_MAP[pageId];
  if(!spec)return isAdmin();
  return hasPermission(spec[0],spec[1]);
}
const ACTION_PERMISSION_MAP={
 customer:["Customers","Create"], booking:["Rooms","Create"], order:["Restaurant","Create"], expense:["Expenses","Create"], feedback_update:["Customers","Update"], maps_config:["Hotel","Update"], nearby_create:["Hotel","Create"], nearby_status:["Hotel","Update"], route_create:["Hotel","Create"], media_create:["Hotel","Create"], media_update:["Hotel","Update"], media_status:["Hotel","Update"], transport:["Hotel","Create"], transport_update:["Hotel","Update"],
 room_create:["Rooms","Create"],
room_update:["Rooms","Update"],
room_payment_create:["Billing","Create"],
 backup:["Users","Create"], guest_update:["Customers","Update"], room_status:["Rooms","Update"], order_status:["Restaurant","Update"], table_status:["Tables","Update"], table_create:["Tables","Create"], inventory_stock:["Inventory","Create"], notification_read:["Reports","Update"]
};
function isActionAllowed(actionName){const spec=ACTION_PERMISSION_MAP[actionName];if(!spec)return isAdmin();return hasPermission(spec[0],spec[1]);}
function showAccessDenied(){document.getElementById("page").innerHTML=`${pageHead("Access Restricted","Your current role does not have permission to view this module.")}<div class="card danger"><h3>Permission required</h3><p class="section-note">Ask an administrator to grant the required permission. The FastAPI backend remains the final authorization boundary.</p></div>`;}
function buildNav(){const nav=document.getElementById("nav");nav.innerHTML="";NAV.forEach(group=>{const allowed=group.items.filter(([id])=>canOpenPage(id));if(!allowed.length)return;const sec=document.createElement("div");sec.className="nav-section";sec.textContent=group.section;nav.appendChild(sec);allowed.forEach(([id,icon,label])=>{const b=document.createElement("button");b.className="nav-item";b.dataset.page=id;b.innerHTML=`<span class="nav-icon">${icon}</span><span>${esc(label)}</span>`;b.onclick=()=>{if(!canOpenPage(id)){showAccessDenied();return;}state.page=id;render();document.getElementById("sidebar").classList.remove("open")};nav.appendChild(b)})})}
function setTop(){const labels={};NAV.forEach(g=>g.items.forEach(x=>labels[x[0]]=x[2]));const kitchen=currentRole()==="kitchen";const label=labels[state.page]||"Dashboard";const crumb=document.getElementById("breadcrumb");if(crumb)crumb.textContent=kitchen?"YADAV HOTEL":(state.page==="dashboard"?"Dashboard":`Dashboard / ${label}`);if(state.user){document.getElementById("user-label").textContent=state.user.username||"User";document.getElementById("user-avatar").textContent=(state.user.username||"U")[0].toUpperCase();const h=state.hotelContext||{};const hotelLabel=h.hotel_name?`${h.hotel_name} • ${h.hotel_code||`Hotel ID ${state.user.hotel_id}`}`:(state.user.hotel_id?`Hotel ID ${state.user.hotel_id}`:"Hotel context");document.getElementById("hotel-context").textContent=kitchen?"Kitchen Dashboard":hotelLabel}}
async function refreshNotificationBadge(){const el=document.getElementById("notification-count");if(!el||!state.token)return;try{const r=await api("/notifications?unread_only=true&limit=1");const count=Number(r.data?.length||0);el.textContent=count>99?"99+":String(count);el.classList.toggle("hidden",count===0)}catch{el.classList.add("hidden")}}
function closeSidebar(){document.getElementById("sidebar")?.classList.remove("open");document.getElementById("sidebar-overlay")?.classList.add("hidden");}
function openSidebar(){document.getElementById("sidebar")?.classList.add("open");document.getElementById("sidebar-overlay")?.classList.remove("hidden");}
function openUserProfile(){const u=state.user||{};const b=document.createElement("div");b.className="modal-backdrop";b.innerHTML=`<div class="modal profile-modal"><div class="page-head"><div><h2>User Profile</h2><span class="section-note">Current dashboard session</span></div><button data-close>✕</button></div><div class="profile-grid"><div class="profile-avatar">${esc((u.username||"U")[0].toUpperCase())}</div><div><strong>${esc(u.username||"User")}</strong><p class="section-note">Role: ${esc(u.role||"—")}</p><p class="section-note">Hotel: ${esc(u.hotel_id??"—")}</p><p class="section-note">Staff: ${esc(u.staff_name||"—")}</p></div></div><div class="form-actions"><button data-close>Close</button><button class="primary" data-password>Change Password</button></div></div>`;document.body.appendChild(b);b.querySelectorAll("[data-close]").forEach(x=>x.onclick=()=>b.remove());b.querySelector("[data-password]").onclick=()=>{b.remove();openPasswordChange()};}

function setActive(){document.querySelectorAll(".nav-item").forEach(x=>x.classList.toggle("active",x.dataset.page===state.page));}
function showObjectModal(title,obj){const b=document.createElement("div");b.className="modal-backdrop";b.innerHTML=`<div class="modal"><div class="page-head"><div><h2>${esc(title)}</h2><span class="section-note">Read-only details</span></div><button data-close>✕</button></div>${table([obj])}<div class="form-actions"><button data-close>Close</button></div></div>`;document.body.appendChild(b);b.querySelectorAll("[data-close]").forEach(x=>x.onclick=()=>b.remove())}
function showRoomDetailsModal(title,rows){
 const b=document.createElement("div");b.className="modal-backdrop";
 b.innerHTML=`<div class="modal room-details-modal"><div class="page-head"><div><h2>${esc(title)}</h2><span class="section-note">Read-only room details</span></div><button data-close>✕</button></div>${table(rows||[])}<div class="form-actions"><button data-close>Close</button></div></div>`;
 document.body.appendChild(b);b.querySelectorAll("[data-close]").forEach(x=>x.onclick=()=>b.remove());
}
function restaurantOrderItems(value){
  let raw=value;
  if(typeof raw==="string"){
    try{raw=JSON.parse(raw)}catch{return []}
  }
  if(!Array.isArray(raw))return [];
  return raw.map(item=>({
    item_id:item?.item_id||item?.menu_item_id||"",
    name:item?.name||item?.item_name||item?.menu_item_name||item?.title||"Unknown item",
    quantity:Number(item?.quantity??item?.qty??1),
    price:Number(item?.price??item?.unit_price??0),
    subtotal:Number(item?.subtotal??item?.amount??((Number(item?.price??item?.unit_price??0))*(Number(item?.quantity??item?.qty??1))))
  }));
}
function restaurantKitchenItemsHtml(row){
  const items=restaurantOrderItems(row?.cart??row?.items??row?.order_items);
  if(!items.length)return '<div class="section-note">No item details available for this order.</div>';
  return `<div class="restaurant-kitchen-items"><table class="data-table"><thead><tr><th>Item</th><th>Qty</th><th>Unit Price</th><th>Amount</th></tr></thead><tbody>${items.map(item=>`<tr><td><strong>${esc(item.name)}</strong><div class="section-note">${esc(item.item_id)}</div></td><td><strong>${esc(item.quantity)}</strong></td><td>${money(item.price)}</td><td>${money(item.subtotal)}</td></tr>`).join("")}</tbody></table></div>`;
}
function restaurantKitchenDetailModal(row){
  const b=document.createElement("div");b.className="modal-backdrop";
  const orderId=row?.order_id||"";
  const items=restaurantOrderItems(row?.cart??row?.items??row?.order_items);
  const itemCount=items.reduce((sum,item)=>sum+Math.max(0,Number(item.quantity||0)),0);
  b.innerHTML=`<div class="modal" style="max-width:980px;width:min(980px,94vw)">
    <div class="page-head"><div><h2>Kitchen Order ${esc(orderId)}</h2><span class="section-note">Kitchen preparation details</span></div><button data-close>✕</button></div>
    <div class="grid cards" style="margin:0 0 15px">
      ${metric("Table",row?.table_number||"—","Table number","blue","▣")}
      ${metric("Guest",row?.customer_name||"—","Customer","purple","♙")}
      ${metric("Status",row?.order_status||"—","Kitchen status","orange","⌁")}
      ${metric("Items",itemCount,"Total quantity","green","✓")}
    </div>
    <div class="card" style="margin-bottom:15px"><div class="section-toolbar"><div><h3>Items to Prepare</h3><p class="section-note">Each menu item and required quantity for this kitchen order.</p></div></div>${restaurantKitchenItemsHtml(row)}</div>
    <div class="card"><div class="section-toolbar"><div><h3>Order Information</h3><p class="section-note">Order timing and financial summary.</p></div></div>${table([[{label:"Order ID",value:orderId},{label:"Order Date",value:row?.order_date||"—"},{label:"Order Time",value:row?.order_time||"—"},{label:"Subtotal",value:money(row?.subtotal||0)},{label:"GST",value:money(row?.gst||0)},{label:"Grand Total",value:money(row?.grand_total||0)}].reduce((acc,x)=>(acc[x.label]=x.value,acc),{})])}</div>
    <div class="form-actions"><button data-close>Close</button></div>
  </div>`;
  document.body.appendChild(b);b.querySelectorAll("[data-close]").forEach(x=>x.onclick=()=>b.remove());
}
function table(rows,actions=""){
  if(!Array.isArray(rows)||!rows.length)return `<div class="empty">No records found.</div>`;
  const keys=[...new Set(rows.flatMap(r=>Object.keys(r||{})))].slice(0,12);
  const head=keys.map(k=>`<th>${esc(k.replaceAll("_"," "))}</th>`).join("")+(actions?`<th>Actions</th>`:"");
  const body=rows.map((r,i)=>{const actionHtml=typeof actions==="function"?actions(r,i):actions;return `<tr>${keys.map(k=>`<td>${cell(r[k])}</td>`).join("")}${actionHtml?`<td>${String(actionHtml).replaceAll("{{i}}",i)}</td>`:""}</tr>`}).join("");
  return `<div class="table-wrap"><table class="data-table"><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table></div>`;
}
function paginatedTable(rows,actions="",key="list",pageSize=25){
  if(!Array.isArray(rows)||!rows.length)return `<div class="empty">No records found.</div>`;
  const total=rows.length, pages=Math.max(1,Math.ceil(total/pageSize));
  const current=Math.min(Math.max(1,Number(state.listPages[key]||1)),pages); state.listPages[key]=current;
  const start=(current-1)*pageSize, visible=rows.slice(start,start+pageSize);
  const keys=[...new Set(rows.flatMap(r=>Object.keys(r||{})))].slice(0,12);
  const head=keys.map(k=>`<th>${esc(k.replaceAll("_"," "))}</th>`).join("")+(actions?`<th>Actions</th>`:"");
  const body=visible.map((r,i)=>{const idx=start+i;const actionHtml=typeof actions==="function"?actions(r,idx):actions;return `<tr>${keys.map(k=>`<td>${cell(r[k])}</td>`).join("")}${actionHtml?`<td>${String(actionHtml).replaceAll("{{i}}",idx)}</td>`:""}</tr>`}).join("");
  const nav=pages>1?`<div class="pagination" role="navigation" aria-label="Pagination"><button type="button" data-page-prev="${esc(key)}" ${current===1?"disabled":""}>Previous</button><span>Page ${current} of ${pages} · ${start+1}-${Math.min(start+pageSize,total)} of ${total}</span><button type="button" data-page-next="${esc(key)}" ${current===pages?"disabled":""}>Next</button></div>`:"";
  return `<div class="table-wrap"><table class="data-table"><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table></div>${nav}`;
}
function cell(v){if(v===null||v===undefined)return "—";if(typeof v==="object")return esc(JSON.stringify(v));const s=String(v);if(s.length>90)return `<span title="${esc(s)}">${esc(s.slice(0,87))}…</span>`;return esc(s);}
async function listCard(title,path,opts={}){const r=await api(path);const rows=r.data||[];return `<div class="card"><div class="page-head"><div><h3>${esc(title)}</h3><span class="section-note">${rows.length} record(s)</span></div>${opts.action||""}</div>${table(rows,opts.actions||"")}</div>`}
function formModal(title,fields,onSubmit){
  const b=document.createElement("div");
  b.className="modal-backdrop";

  b.innerHTML=`
    <div class="modal">
      <div class="page-head">
        <div>
          <h2>${esc(title)}</h2>
          <span class="section-note">Enter validated information</span>
        </div>
        <button data-close>✕</button>
      </div>

      <form class="form-grid">
        ${fields.map(f=>`
          <label class="${f.full?'full':''}">
            ${esc(f.label)}
            ${
              f.type==="select"
              ? `<select name="${esc(f.name)}">
                  ${(f.options||[]).map(o=>`
                    <option value="${esc(o)}" ${String(o)===String(f.value??"")?"selected":""}>
                      ${esc(o)}
                    </option>
                  `).join("")}
                </select>`
              : `<input
                  name="${esc(f.name)}"
                  type="${f.type||"text"}"
                  ${f.type==="file"?`accept="${esc(f.accept||".pdf,.jpg,.jpeg,.png")}"`:""}
                  ${f.required===false?"":"required"}
                  ${f.type==="file"?"":(f.value!==undefined?`value="${esc(f.value)}"`:"")}
                  ${f.placeholder?`placeholder="${esc(f.placeholder)}"`:""}
                >`
            }
          </label>
        `).join("")}

        <div class="full form-actions">
          <button type="button" data-close>Cancel</button>
          <button class="primary" type="submit">Save</button>
        </div>

        <p class="form-error full" data-error></p>
      </form>
    </div>
  `;

  document.body.appendChild(b);

  // New Guest: look up the existing Guest Master by exact mobile before allowing duplicate creation.
  let matchedGuestForSubmit=null;
  if(title === "New Guest"){
    const mobileInput=b.querySelector('input[name="customer_mobile"]');
    const nameInput=b.querySelector('input[name="customer_name"]');
    const mobileLabel=mobileInput?.closest("label");
    const lookupWrap=document.createElement("div");
    lookupWrap.className="guest-existing-match";
    lookupWrap.style.cssText="display:grid;gap:8px;margin-top:8px";
    const lookupNote=document.createElement("span");
    lookupNote.className="section-note";
    lookupNote.setAttribute("aria-live","polite");
    const useExistingButton=document.createElement("button");
    useExistingButton.type="button";
    useExistingButton.className="primary";
    useExistingButton.textContent="Use Existing Guest Profile";
    useExistingButton.hidden=true;
    const uploadExistingButton=document.createElement("button");
    uploadExistingButton.type="button";
    uploadExistingButton.textContent="Upload ID to Existing Guest";
    uploadExistingButton.hidden=true;
    if(mobileLabel){mobileLabel.appendChild(lookupWrap);lookupWrap.append(lookupNote,useExistingButton,uploadExistingButton);}
    let lookupTimer=null, lookupToken=0, matchedGuest=null;
    const fieldNames=["customer_name","customer_mobile","customer_email","customer_address","customer_city","customer_state","customer_country","customer_pincode","government_id_type","government_id_status","preferences","special_requests","guest_notes"];
    function fillExistingGuest(guest){
      fieldNames.forEach(name=>{
        const input=b.querySelector(`[name="${name}"]`);
        if(input && guest[name]!==undefined && guest[name]!==null){
          input.value=String(guest[name]);
          input.dispatchEvent(new Event("change",{bubbles:true}));
        }
      });
    }
    useExistingButton.addEventListener("click",()=>{
      if(!matchedGuest)return;
      fillExistingGuest(matchedGuest);
      const form=b.querySelector("form");
      const submit=form?.querySelector('button[type="submit"]');
      if(submit)submit.disabled=true;
      lookupNote.textContent=`Selected existing profile ${matchedGuest.customer_id}. This form will not create a duplicate. Close this form and use this Guest from the reservation or restaurant guest selector.`;
      useExistingButton.hidden=true;
      toast(`Existing Guest selected: ${matchedGuest.customer_id}`);
    });
    uploadExistingButton.addEventListener("click",async()=>{
      if(!matchedGuest)return;
      const file=b.querySelector('input[name="government_id_document"]')?.files?.[0];
      const idType=b.querySelector('select[name="government_id_type"]')?.value;
      if(!file){lookupNote.textContent="Choose an ID document first.";lookupNote.style.color="var(--danger,#b42318)";return;}
      if(!idType){lookupNote.textContent="Select the Government ID Type first.";lookupNote.style.color="var(--danger,#b42318)";return;}
      try{
        const uploadData=new FormData();uploadData.append("id_type",idType);uploadData.append("document",file,file.name);
        const response=await fetch(API+`/customers/${encodeURIComponent(matchedGuest.customer_id)}/government-id`,{method:"POST",headers:state.token?{Authorization:`Bearer ${state.token}`}:{},body:uploadData});
        const text=await response.text();let body={};try{body=text?JSON.parse(text):{}}catch{}
        if(!response.ok)throw new Error(body.detail||`ID upload failed (${response.status}).`);
        matchedGuest.government_id_type=idType;matchedGuest.government_id_status="Pending Verification";
        const statusSelect=b.querySelector('select[name="government_id_status"]');if(statusSelect)statusSelect.value="Pending Verification";
        lookupNote.textContent=`ID uploaded securely for ${matchedGuest.customer_id}. Verification is pending.`;lookupNote.style.color="var(--success,#16a34a)";
        toast("Identity document uploaded securely.");
      }catch(err){lookupNote.textContent=err.message||"ID upload failed.";lookupNote.style.color="var(--danger,#b42318)";}
    });
    mobileInput?.addEventListener("input",()=>{
      window.clearTimeout(lookupTimer);
      const mobile=String(mobileInput.value||"").trim();
      matchedGuest=null;
      matchedGuestForSubmit=null;
      useExistingButton.hidden=true;
      uploadExistingButton.hidden=true;
      lookupNote.textContent="";
      const submit=b.querySelector('button[type="submit"]');
      if(submit)submit.disabled=false;
      if(mobile.length<5)return;
      lookupTimer=window.setTimeout(async()=>{
        const token=++lookupToken;
        try{
          const result=await api(`/customers/lookup/mobile?mobile=${encodeURIComponent(mobile)}`);
          if(token!==lookupToken || String(mobileInput.value||"").trim()!==mobile)return;
          if(result?.found && result.data){
            matchedGuest=result.data;
            matchedGuestForSubmit=result.data;
            lookupNote.textContent=`Existing guest found: ${result.data.customer_name} · ${result.data.customer_id}.`;
            lookupNote.style.color="var(--success,#16a34a)";
            useExistingButton.hidden=false;
            uploadExistingButton.hidden=false;
          }else{
            lookupNote.textContent="No existing guest found for this mobile number.";
            lookupNote.style.color="";
          }
        }catch(err){lookupNote.textContent=err.message||"Guest lookup unavailable.";lookupNote.style.color="var(--danger,#b42318)";}
      },350);
    });
  }

  b.querySelectorAll("[data-close]").forEach(x=>{
    x.onclick=()=>b.remove();
  });

  b.querySelector("form").onsubmit=async e=>{
    e.preventDefault();

    const fd=new FormData(e.target);
    const obj={};

    fields.forEach(f=>{
      let v=fd.get(f.name);

      if(f.type==="file") return;
      if(f.type==="number" && v!==""){
        v=Number(v);
      }

      obj[f.name]=v||undefined;
    });

    try{
      if(title==="New Guest" && matchedGuestForSubmit){
        throw new Error(`Guest already exists as ${matchedGuestForSubmit.customer_id}. Choose “Use Existing Guest Profile”; a duplicate account will not be created.`);
      }
      const savedResult=await onSubmit(obj);
      let uploadError="";
      if(title==="New Guest"){
        const fileInput=b.querySelector('input[name="government_id_document"]');
        const file=fileInput?.files?.[0];
        const customerId=savedResult?.data?.customer_id;
        const idType=b.querySelector('select[name="government_id_type"]')?.value;
        if(file && customerId && idType){
          try{
            const uploadData=new FormData();
            uploadData.append("id_type",idType);
            uploadData.append("document",file,file.name);
            const uploadResponse=await fetch(API+`/customers/${encodeURIComponent(customerId)}/government-id`,{
              method:"POST",
              headers:state.token?{Authorization:`Bearer ${state.token}`}:{},
              body:uploadData
            });
            const uploadText=await uploadResponse.text();
            let uploadBody={};try{uploadBody=uploadText?JSON.parse(uploadText):{}}catch{}
            if(!uploadResponse.ok)throw new Error(uploadBody.detail||`ID upload failed (${uploadResponse.status}).`);
          }catch(uploadErr){uploadError=uploadErr?.message||"ID upload failed.";}
        }else if(file && !idType){uploadError="Guest was created, but ID upload was skipped because no Government ID Type was selected.";}
      }
      b.remove();
      if(uploadError)toast(`Guest saved. ${uploadError}`,true);else toast("Saved successfully.");
      render();
    }catch(err){
      const message =
        err?.message ||
        err?.detail ||
        (typeof err==="string" ? err : JSON.stringify(err));

      b.querySelector("[data-error]").textContent=message;
    }
  };
}
async function openRestaurantOrderModal(){
  if(!isActionAllowed("order")){showAccessDenied();return;}
  try{
    const [menuResponse,tablesResponse]=await Promise.all([
      api("/restaurant/menu"),
      api("/tables")
    ]);
    const menu=(menuResponse.data||[]).filter(x=>Boolean(Number(x.is_available)));
    const tables=(tablesResponse.data||[]).filter(x=>String(x.table_status||"").toLowerCase()==="occupied");

    if(!menu.length){
      toast("No active restaurant menu items are available.",true);
      return;
    }
    if(!tables.length){
      toast("No occupied restaurant table is available for a new order. Mark a table as occupied first.",true);
      return;
    }

    const b=document.createElement("div");
    b.className="modal-backdrop";
    b.innerHTML=`
      <div class="modal">
        <div class="page-head">
          <div>
            <h2>Restaurant Order</h2>
            <span class="section-note">Create an order using active menu items</span>
          </div>
          <button type="button" data-close>✕</button>
        </div>

        <form class="form-grid" data-restaurant-order-form>
          <label>
            Guest name
            <input name="customer_name" type="text" required placeholder="Guest name">
          </label>
          <label>
            Mobile
            <input name="customer_mobile" type="text" required placeholder="Mobile number">
          </label>

          <label>
            Table
            <select name="table_number" required>
              <option value="">Select occupied table</option>
              ${tables.map(t=>`<option value="${esc(t.table_number)}">${esc(t.table_number)}${t.capacity?` — ${esc(t.capacity)} seats`:""}</option>`).join("")}
            </select>
          </label>
          <label>
            Customer ID
            <input name="customer_id" type="text" placeholder="Optional">
          </label>

          <div class="full">
            <label>
              Items
              <div class="restaurant-order-item-picker">
                <select data-order-item>
                  <option value="">Select menu item</option>
                  ${menu.map(i=>`<option value="${esc(i.item_id)}" data-price="${esc(i.price)}">${esc(i.item_name)} — ${money(i.price)}</option>`).join("")}
                </select>
                <input data-order-qty type="number" min="1" step="1" value="1" aria-label="Quantity" placeholder="Qty">
                <button type="button" data-order-add-item>Add Item</button>
              </div>
            </label>

            <div class="card" style="margin-top:10px">
              <div class="section-toolbar">
                <div>
                  <strong>Selected Items</strong>
                  <div class="section-note">Add one or more menu items to this order.</div>
                </div>
              </div>
              <div data-order-cart>
                <div class="section-note">No items added yet.</div>
              </div>
            </div>
          </div>

          <label>
            Discount (₹)
            <input name="discount" type="number" min="0" step="0.01" value="0">
          </label>
          <label>
            Payment method
            <select name="payment_method">
              <option value="">Not paid yet</option>
              <option value="Cash">Cash</option>
              <option value="UPI">UPI</option>
              <option value="Card">Card</option>
              <option value="Online">Online</option>
              <option value="Other">Other</option>
            </select>
          </label>

          <label>
            Paid amount (₹)
            <input name="paid_amount" type="number" min="0" step="0.01" value="0">
          </label>
          <label>
            Advance (₹)
            <input name="advance_amount" type="number" min="0" step="0.01" value="0">
          </label>

          <label class="full">
            Notes
            <input name="order_notes" type="text" placeholder="Optional note">
          </label>

          <div class="full card" data-order-summary>
            <div class="section-toolbar">
              <strong>Order Summary</strong>
              <span data-order-total>₹0</span>
            </div>
            <div class="section-note" data-order-breakdown>Subtotal ₹0 • GST 5% ₹0 • Discount ₹0 • Balance ₹0</div>
          </div>

          <div class="full form-actions">
            <button type="button" data-close>Cancel</button>
            <button class="primary" type="submit">Save Order</button>
          </div>
          <p class="form-error full" data-error></p>
        </form>
      </div>
    `;

    document.body.appendChild(b);

    const cart=[];
    const form=b.querySelector("[data-restaurant-order-form]");
    const itemSelect=b.querySelector("[data-order-item]");
    const qtyInput=b.querySelector("[data-order-qty]");
    const cartEl=b.querySelector("[data-order-cart]");
    const discountInput=form.querySelector('[name="discount"]');
    const paidInput=form.querySelector('[name="paid_amount"]');
    const advanceInput=form.querySelector('[name="advance_amount"]');
    const totalEl=b.querySelector("[data-order-total]");
    const breakdownEl=b.querySelector("[data-order-breakdown]");

    const close=()=>b.remove();
    b.querySelectorAll("[data-close]").forEach(x=>x.onclick=close);

    function totals(){
      const subtotal=cart.reduce((sum,i)=>sum+(i.price*i.quantity),0);
      const discount=Math.max(0,Number(discountInput.value||0));
      const taxable=Math.max(0,subtotal-discount);
      const gst=taxable*0.05;
      const grandTotal=taxable+gst;
      const paid=Math.max(0,Number(paidInput.value||0));
      const balance=Math.max(0,grandTotal-paid);
      return {subtotal,discount,taxable,gst,grandTotal,paid,balance};
    }

    function renderCart(){
      if(!cart.length){
        cartEl.innerHTML='<div class="section-note">No items added yet.</div>';
      }else{
        cartEl.innerHTML=`
          <div class="table-wrap">
            <table class="data-table">
              <thead><tr><th>Item</th><th>Price</th><th>Qty</th><th>Amount</th><th></th></tr></thead>
              <tbody>
                ${cart.map((i,index)=>`
                  <tr>
                    <td>${esc(i.name)}</td>
                    <td>${money(i.price)}</td>
                    <td>${esc(i.quantity)}</td>
                    <td>${money(i.price*i.quantity)}</td>
                    <td><button type="button" data-order-remove="${index}">Remove</button></td>
                  </tr>
                `).join("")}
              </tbody>
            </table>
          </div>`;
        cartEl.querySelectorAll("[data-order-remove]").forEach(btn=>{
          btn.onclick=()=>{
            cart.splice(Number(btn.dataset.orderRemove),1);
            renderCart();
            renderTotals();
          };
        });
      }
    }

    function renderTotals(){
      const t=totals();
      totalEl.textContent=money(t.grandTotal);
      breakdownEl.textContent=`Subtotal ${money(t.subtotal)} • GST 5% ${money(t.gst)} • Discount ${money(t.discount)} • Balance ${money(t.balance)}`;
    }

    b.querySelector("[data-order-add-item]").onclick=()=>{
      const itemId=itemSelect.value;
      const qty=Math.floor(Number(qtyInput.value||0));
      if(!itemId){toast("Select a menu item first.",true);return;}
      if(qty<1){toast("Quantity must be at least 1.",true);return;}
      const selected=menu.find(i=>String(i.item_id)===String(itemId));
      if(!selected)return;
      const existing=cart.find(i=>i.item_id===selected.item_id);
      if(existing) existing.quantity+=qty;
      else cart.push({item_id:selected.item_id,name:selected.item_name,price:Number(selected.price||0),quantity:qty});
      itemSelect.value="";
      qtyInput.value="1";
      renderCart();
      renderTotals();
    };

    [discountInput,paidInput,advanceInput].forEach(input=>input.addEventListener("input",renderTotals));

    form.onsubmit=async e=>{
      e.preventDefault();
      const errorEl=b.querySelector("[data-error]");
      errorEl.textContent="";
      const t=totals();

      if(!cart.length){errorEl.textContent="Add at least one menu item.";return;}
      if(t.discount>t.subtotal){errorEl.textContent="Discount cannot be greater than the subtotal.";return;}
      if(t.paid>t.grandTotal+0.01){errorEl.textContent="Paid amount cannot be greater than the order total.";return;}
      const advance=Math.max(0,Number(advanceInput.value||0));
      if(advance>t.grandTotal+0.01){errorEl.textContent="Advance cannot be greater than the order total.";return;}

      const fd=new FormData(form);
      const payload={
        customer_name:String(fd.get("customer_name")||"").trim(),
        customer_mobile:String(fd.get("customer_mobile")||"").trim(),
        table_number:String(fd.get("table_number")||"").trim(),
        customer_id:String(fd.get("customer_id")||"").trim()||undefined,
        items:cart.map(i=>({item_id:i.item_id,quantity:i.quantity})),
        discount:t.discount,
        payment_method:String(fd.get("payment_method")||"").trim()||undefined,
        paid_amount:t.paid,
        advance_amount:advance,
        order_notes:String(fd.get("order_notes")||"").trim()||undefined
      };

      try{
        await api("/restaurant/orders",{method:"POST",body:JSON.stringify(payload)});
        close();
        toast("Restaurant order created successfully.");
        render();
      }catch(err){
        errorEl.textContent=err?.message||"Unable to create restaurant order.";
      }
    };
  }catch(e){
    toast(e?.message||"Unable to open Restaurant Order.",true);
  }
}

function pageHead(title,sub="",actions=""){return `<div class="page-head"><div><h1>${esc(title)}</h1><div class="section-note">${esc(sub)}</div></div><div class="actions">${actions}</div></div>`}
async function dashboard(){
  const d=(await api("/dashboard/home")).data||{};
  return pageHead("Dashboard","Hotel operating and financial summary",`<button class="primary" data-refresh>Refresh</button>`)
    +`<div class="card revenue-summary" style="margin-bottom:15px"><div class="page-head" style="margin-bottom:12px"><div><h2>Revenue & Collections</h2><div class="section-note">Overall hotel financial position plus today's business</div></div></div><div class="grid cards">
      ${metric("Total Sales",money(d.total_sales),`Room ${money(d.room_sales)} • Restaurant ${money(d.restaurant_sales)}`,"gold","₹")}
      ${metric("Total Collected",money(d.total_collected),`Room ${money(d.room_collected)} • Restaurant ${money(d.restaurant_collected)}`,"green","✓")}
      ${metric("Outstanding",money(d.total_outstanding),`Room ${money(d.room_outstanding)} • Restaurant ${money(d.restaurant_outstanding)}`,"rose","₹")}
      ${metric("Today's Revenue",money(d.today_total_revenue),`Room ${money(d.today_room_revenue)} • Restaurant ${money(d.today_restaurant_revenue)}`,"purple","▣")}
    </div></div>`
    +`<div class="grid cards">
      ${metric("Today's Bookings",d.bookings,"Reservations for today","purple","▣")}
      ${metric("Today's Check-ins",d.check_ins,"Expected/recorded arrivals","green","✓")}
      ${metric("Today's Check-outs",d.check_outs,"Expected departures","orange","↗")}
      ${metric("Occupancy",Number(d.occupancy_pct||0).toFixed(1)+"%",`${d.occupied_rooms||0} occupied / ${d.total_rooms||0} rooms`,"blue","◉")}
      ${metric("Restaurant Orders",d.restaurant_orders,"Today's non-cancelled orders","teal","⌁")}
      ${metric("Pending Payments",d.pending_payments,"Outstanding room/order balances","rose","₹")}
      ${metric("Low-stock Alerts",d.low_stock_alerts,"Items at or below reorder level","amber","!")}
      ${metric("Guest Issues",d.pending_guest_issues,"Open complaint/issue records","red","⚠")}
      ${metric("Transportation",d.transportation_requests,"Active transportation requests","cyan","⇄")}
    </div>
    <div class="grid two" style="margin-top:15px">
      <div class="card"><h3>Hotel Overview</h3><div class="kpi-row">${metric("Total Rooms",d.total_rooms,"Active room inventory")}${metric("Available",d.available_rooms,"Not currently occupied")}</div></div>
      <div class="card"><h3>Quick Actions</h3><div class="kpi-row" style="margin-top:14px">
        <button data-action="customer">+ Guest</button><button data-action="booking">+ Reservation</button><button data-action="expense">+ Expense</button><button data-action="transport">+ Transport</button>
      </div></div>
    </div>`;
}

function metric(label,value,sub,tone="default",icon="•"){return `<div class="card metric metric-${esc(tone)}"><div class="metric-top"><div class="label">${esc(label)}</div><span class="metric-icon" aria-hidden="true">${esc(icon)}</span></div><div class="value">${esc(value)}</div><div class="sub">${esc(sub)}</div></div>`}
function revenueBars(d){const vals=[Number(d.room_revenue||0),Number(d.restaurant_revenue||0),Number(d.total_revenue||0)];const max=Math.max(...vals,1);return `<div class="chart">${vals.map((v,i)=>`<div class="bar" style="height:${Math.max(8,v/max*140)}px"><b>${money(v)}</b><span>${["Room","Restaurant","Total"][i]}</span></div>`).join("")}</div>`}
async function generic(title,sub,path,opts={}){
  const q=opts.search?`?search=${encodeURIComponent(opts.search)}`:"";const r=await api(path+q);const rows=r.data||[];
  let actions=opts.actions||"";let head=pageHead(title,sub,opts.buttons||"");
  return head+`<div class="toolbar"><input class="search" id="page-search" placeholder="Search current list…" value="${esc(opts.search||"")}"><button id="do-search">Search</button><button id="clear-search">Clear</button></div><div class="card">${paginatedTable(rows,actions,`generic:${path}`,25)}</div>`;
}
async function frontdesk(){
  const d=(await api("/frontdesk")).data||{};
  const arrivals=d.arrivals||[], departures=d.departures||[], current=d.current_guests||[], pendingIn=d.pending_checkins||[], pendingOut=d.pending_checkouts||[], available=d.available_rooms||[], occupied=d.occupied_rooms||[];
  const rows=d.reservation_results||[];
  const rowActions=(row)=>`<button data-open-booking="${esc(row.booking_id||"")}">View</button> ${isActionAllowed("room_status")&&/pending|confirmed/i.test(row.booking_status||"")?`<button data-front-action="check-in" data-booking-id="${esc(row.booking_id||"")}">Quick Check-in</button>`:""} ${isActionAllowed("room_status")&&/checked.?in|occupied/i.test(row.booking_status||"")?`<button data-front-action="check-out" data-booking-id="${esc(row.booking_id||"")}">Quick Check-out</button>`:""}`;
  const guestTable=rows.length?table(rows,rowActions):`<div class="empty-state">No reservations found.</div>`;
  return pageHead("Front Desk","Reception operations for today's arrivals, departures and current guests",`<button class="primary" data-action="booking">New Reservation</button>`)
    +`<div class="grid cards">${metric("Today's Arrivals",arrivals.length,"Expected arrivals")}${metric("Today's Departures",departures.length,"Expected departures")}${metric("Current Guests",current.length,"Checked-in guests")}${metric("Available Rooms",available.length,"Ready for allocation")}${metric("Occupied Rooms",occupied.length,"Currently occupied")}${metric("Pending Check-ins",pendingIn.length,"Today's arrivals awaiting check-in")}${metric("Pending Check-outs",pendingOut.length,"Today's departures awaiting check-out")}</div>`
    +`<div class="grid two" style="margin-top:15px"><div class="card"><h3>Guest Lookup</h3><div class="toolbar"><input class="search" id="frontdesk-lookup" placeholder="Name, mobile or customer ID…"><button id="frontdesk-lookup-btn">Lookup</button></div><div id="frontdesk-lookup-results"></div></div><div class="card"><h3>Front Desk Actions</h3><div class="kpi-row"><button data-action="booking">New Reservation</button><button data-page="guests">Guest Lookup</button><button data-page="rooms">Room Availability</button></div></div></div>`
    +`<div class="grid two" style="margin-top:15px"><div class="card"><h3>Today's Arrivals</h3>${table(arrivals,rowActions)}</div><div class="card"><h3>Today's Departures</h3>${table(departures,rowActions)}</div></div>`
    +`<div class="grid two" style="margin-top:15px"><div class="card"><h3>Current Guests</h3>${table(current,rowActions)}</div><div class="card"><h3>Available Rooms</h3>${table(available)}</div></div>`
    +`<div class="card" style="margin-top:15px"><h3>Reservation Search</h3><div class="toolbar"><input class="search" id="frontdesk-res-search" placeholder="Booking ID, guest, mobile or room…"><button id="frontdesk-res-search-btn">Search</button><button id="frontdesk-res-clear">Clear</button></div><div id="frontdesk-res-results">${guestTable}</div></div>`;
}
async function hotel(){
  const [p,c,m,media,s,serviceCatalogResponse]=await Promise.all([
    api("/hotel/profile"),
    api("/hotel/context"),
    api("/hotel/maps"),
    api("/hotel/media"),
    api("/hotel/settings"),
    api("/guest-services/catalog")
  ]);
  const info=p.data||{};
  const context=c.data||{};
  const map=m.data||{};
  const mediaRows=Array.isArray(media.data)?media.data:[];
  const settings=Array.isArray(s.data)?s.data:[];
  const guestServicePolicyRows=Array.isArray(serviceCatalogResponse.data)?serviceCatalogResponse.data:[];
  window.__guestServicePolicyRows=guestServicePolicyRows;
  const field=(key,fallback="—")=>info[key]===null||info[key]===undefined||info[key]===""?fallback:info[key];
  const yesNo=(value)=>value?`<span class="status-pill">${esc(value)}</span>`:"—";
  const card=(title,content,note="")=>`<div class="card"><div class="page-head"><div><h3>${esc(title)}</h3>${note?`<span class="section-note">${esc(note)}</span>`:""}</div></div>${content}</div>`;
  const profileRows=[
    {field:"Hotel Name",value:field("hotel_name")},{field:"Owner",value:field("hotel_owner")},
    {field:"Type",value:field("hotel_type")},{field:"Established",value:field("hotel_established")},
    {field:"Description",value:field("hotel_description")},{field:"Rating",value:field("hotel_rating")},
    {field:"Total Rooms",value:field("total_rooms")}
  ];
  const contactRows=[
    {field:"Mobile",value:field("hotel_mobile")},{field:"Email",value:field("hotel_email")},
    {field:"Website",value:field("hotel_website")},{field:"Support Email",value:field("hotel_support_email")},
    {field:"Support Mobile",value:field("hotel_support_mobile")}
  ];
  const locationRows=[
    {field:"Address",value:field("hotel_address")},{field:"City",value:field("hotel_city")},
    {field:"State",value:field("hotel_state")},{field:"Country",value:field("hotel_country")},
    {field:"PIN Code",value:field("hotel_pincode")}
  ];
  const facilitiesRows=[
    {facility:"Restaurant",status:yesNo(field("restaurant"))},{facility:"Parking",status:yesNo(field("parking"))},
    {facility:"WiFi",status:yesNo(field("wifi"))},{facility:"Laundry",status:yesNo(field("laundry"))}
  ];
  const timingRows=[
    {item:"Check-in",value:field("hotel_checkin_time")},{item:"Check-out",value:field("hotel_checkout_time")},
    {item:"Opening",value:field("hotel_opening")},{item:"Closing",value:field("hotel_closing")},
    {item:"Currency",value:field("hotel_currency")},{item:"GST Rate",value:`${(Number(info.gst_rate??0.05)*100).toFixed(2)}%`}
  ];
  const roomRows=[{item:"Total Rooms",value:field("total_rooms")},{item:"Hotel Type",value:field("hotel_type")},{item:"Rating",value:field("hotel_rating")}];
  const contextRows=Object.keys(context).length?[context]:[{hotel_id:state.user?.hotel_id||"—",hotel_name:field("hotel_name")}];
  const aiText=[
    `${field("hotel_name")} is a ${field("hotel_type")} established in ${field("hotel_established")}.`,
    `${field("hotel_description")}.`,
    `Located in ${field("hotel_city")}, ${field("hotel_state")}, ${field("hotel_country")} ${field("hotel_pincode")}.`,
    `The hotel has ${field("total_rooms")} rooms and offers restaurant, parking, WiFi and laundry facilities.`,
    `Check-in is ${field("hotel_checkin_time")} and check-out is ${field("hotel_checkout_time")}.`,
    `Guest support: ${field("hotel_support_mobile")} / ${field("hotel_support_email")}.`
  ].join(" ");
  const mapRows=Object.keys(map).length?[map]:[{status:"No map configuration available"}];
  return pageHead("Hotel Information","Master information and guest-facing configuration")+
    `<div class="grid two">`+
    card("Hotel Profile",table(profileRows),"Core hotel identity")+
    card("Contact Information",table(contactRows),"Guest and support contacts")+
    card("Hotel Facilities",table(facilitiesRows),"Available guest facilities")+
    card("Hotel Timings",table(timingRows),"Operating and stay timings")+
    card("Location",table(locationRows),"Registered hotel address")+
    card("Hotel Policies",`<div class="section-note">Policy master content is served from the existing hotel information/settings foundation. No policy text is invented by the dashboard.</div>${table(settings)}`,"Existing policy/settings source")+
    card("Guest Services",`<div class="section-note">Configure service-specific No-Show, cancellation and refund rules. Changes are saved to this hotel's Guest Service Catalog.</div><div class="table-wrap"><table><thead><tr><th>Service</th><th>Billing Mode</th><th>No-Show Policy</th><th>Cancellation Fee</th><th>Refund Policy</th><th>Manager Approval</th><th>Action</th></tr></thead><tbody>${guestServicePolicyRows.map((row,index)=>`<tr><td>${esc(row.service_name||"Guest Service")}</td><td>${esc(row.billing_mode||"—")}</td><td>${esc(row.no_show_policy||"No Charge")}</td><td>${esc(row.cancellation_fee_type||"Fixed")} · ${Number(row.cancellation_fee_value||0)}${row.cancellation_fee_type==="Percent"?"%":" ₹"}</td><td>${esc(row.refund_policy||"Refund Paid Amount")}</td><td>${Number(row.manager_approval_required)?"Required":"Not required"}</td><td>${hasPermission("Settings","Update")?`<button type="button" data-edit-service-policy="${esc(row.service_id)}">Edit Policy</button>`:"View only"}</td></tr>`).join("")||`<tr><td colspan="7">No guest services configured.</td></tr>`}</tbody></table></div>` ,"Service policies are configurable per hotel; manager overrides must be justified and authorized.")+
    card("Dining Information",`<div class="stat-grid"><div class="metric"><strong>${esc(field("restaurant"))}</strong><span>Restaurant</span></div></div>`,"Dining availability")+
    card("Room Information",table(roomRows),"Room master summary")+
    card("Banquet / Events",`<div class="section-note">Banquet/event capability is part of the hotel's configured business description. Dedicated event master data will remain in the event/banquet module when exposed through the API.</div><p>${esc(field("hotel_description"))}</p>`,"Existing hotel foundation")+
    card("Transportation Information",`<div class="section-note">Transportation requests and provider/integration information are managed through the Transportation module.</div><p>Transportation service is available through the existing transportation dashboard and API foundation.</p>`,"Cross-module information")+
    card("Accessibility",`<div class="section-note">No dedicated accessibility fields are exposed by the current Hotel Information API. The dashboard therefore does not invent accessibility claims.</div>`,"Source-aware display")+
    card("Safety & Security",`<div class="section-note">No dedicated safety/security fields are exposed by the current Hotel Information API. The dashboard therefore does not invent safety claims.</div>`,"Source-aware display")+
    card("Maps",table(mapRows),"Existing Maps & Navigation integration")+
    card("Photos / Media",table(mediaRows),`${mediaRows.length} active media item(s)`)+
    card("AI-readable Hotel Information",`<div class="ai-readable"><p>${esc(aiText)}</p></div>`,"Generated only from existing hotel master data")+
    card("Hotel Context",table(contextRows),"Active hotel scope")+
    `</div>`;
}
async function mapsmedia(){
 const [m,n,r,media]=await Promise.all([api("/hotel/maps"),api("/hotel/nearby-places"),api("/hotel/navigation-routes"),api("/hotel/media?guest_visible_only=false")]);
 const cfg=m.data?.configuration||{}, mapUrl=m.data?.map_url||"";
 const nearby=Array.isArray(n.data)?n.data:[], routes=Array.isArray(r.data)?r.data:[], mediaRows=Array.isArray(media.data)?media.data:[]; window.__nearbyRows=nearby; window.__mediaRows=mediaRows;
 const cfgRows=Object.keys(cfg).length?[cfg]:[{status:"No map configuration"}];
 const nearbyActions=isActionAllowed("nearby_status")?`<button data-nearby-status="{{i}}">Status</button>`:"";
 const mediaActions=`${isActionAllowed("media_update")?`<button data-media-edit="{{i}}">Edit</button>`:""} ${isActionAllowed("media_status")?`<button data-media-status="{{i}}">Status</button>`:""}`;
 return pageHead("Maps & Media","Hotel location, map configuration, nearby places, navigation routes and visual media",`<div class="kpi-row">${mapUrl?`<a class="button primary" href="${esc(mapUrl)}" target="_blank" rel="noopener">Open Hotel Map</a>`:""}${isActionAllowed("maps_config")?`<button data-map-config>Map Configuration</button>`:""}${isActionAllowed("nearby_create")?`<button data-nearby-create>+ Nearby Place</button>`:""}${isActionAllowed("route_create")?`<button data-route-create>+ Route</button>`:""}${isActionAllowed("media_create")?`<button data-media-create>+ Media</button>`:""}</div>`)+
 `<div class="grid two"><div class="card"><h3>Hotel Location & Map Configuration</h3>${table(cfgRows)}</div><div class="card"><h3>Map / Navigation Status</h3>${table([{provider:cfg.map_provider||"—",integration_status:cfg.integration_status||"—",api_enabled:cfg.api_enabled?"Enabled":"Disabled",default_zoom:cfg.default_zoom||"—"}])}</div></div>`+
 `<div class="grid two" style="margin-top:15px"><div class="card"><h3>Nearby Places</h3>${table(nearby,nearbyActions)}</div><div class="card"><h3>Navigation / Routes</h3>${table(routes)}</div></div>`+
 `<div class="card" style="margin-top:15px"><div class="page-head"><div><h3>Photos / Media Gallery</h3><span class="section-note">Categories, metadata, guest visibility and active/inactive status</span></div></div>${table(mediaRows,mediaActions)}</div>`;
}
async function guests(){
 const q=String(state.guestSearch||"").trim(), field=state.guestSearchField||"all", status=state.guestStatus||"";
 const dateType="created", dateFrom=String(state.guestDateFrom||""), dateTo=String(state.guestDateTo||"");
 const params=new URLSearchParams(); if(q)params.set("search",q); params.set("search_field",field); if(status)params.set("guest_status",status); params.set("date_type",dateType); if(dateFrom)params.set("date_from",dateFrom); if(dateTo)params.set("date_to",dateTo);
 const rawRows=(await api("/customers?"+params.toString())).data||[];
 // Normalize legacy/duplicate customer columns into the canonical Guest Master fields.
 const rows=rawRows.map(r=>({
   "Customer ID":r.customer_id||"—",
   "Guest Name":r.customer_name||"—",
   "Mobile":r.customer_mobile||"—",
   "Email":r.customer_email||"—",
   "Address":r.customer_address||"—",
   "City":r.customer_city||"—",
   "State":r.customer_state||"—",
   "Country":r.customer_country||"—",
   "Pincode":r.customer_pincode||"—",
   "Created Time":r.created_time||"—",
   "Status":r.guest_status||"—"
 }));
 const actions=`<button type="button" data-guest-detail="{{i}}">View</button><button type="button" data-guest-edit="{{i}}">Edit</button>`;
 return pageHead("Guests & Customers","Guest master, profiles, relationships and complete guest history",`<button type="button" data-guest-back-dashboard>← Back to Dashboard</button><button class="primary" data-action="customer">+ New Guest</button>`)+
 `<div class="guest-filter-bar" aria-label="Guest search filters">`+
 `<div class="guest-filter-control guest-search-control"><input class="search" id="guest-search" placeholder="Search name, mobile, ID, email…" value="${esc(q)}" aria-label="Search guests"></div>`+
 `<div class="guest-filter-control"><select id="guest-search-field" aria-label="Search field"><option value="all" ${field==="all"?"selected":""}>All fields</option><option value="id" ${field==="id"?"selected":""}>Customer ID</option><option value="name" ${field==="name"?"selected":""}>Name</option><option value="mobile" ${field==="mobile"?"selected":""}>Mobile</option><option value="email" ${field==="email"?"selected":""}>Email</option><option value="city" ${field==="city"?"selected":""}>City</option><option value="state" ${field==="state"?"selected":""}>State</option></select></div>`+
 `<div class="guest-filter-control"><select id="guest-status-filter" aria-label="Guest status"><option value="" ${!status?"selected":""}>All statuses</option><option value="Active" ${status==="Active"?"selected":""}>Active</option><option value="Inactive" ${status==="Inactive"?"selected":""}>Inactive</option><option value="Blacklisted" ${status==="Blacklisted"?"selected":""}>Blacklisted</option></select></div>`+
 `<label class="guest-date-field"><span>Created date from</span><div class="guest-date-input-wrap"><input id="guest-date-from" class="guest-date-input${dateFrom?"":" guest-date-empty"}" type="date" max="${dateNow()}" value="${esc(dateFrom)}" aria-label="Guest created date from"><span class="guest-date-placeholder" aria-hidden="true">DD-MM-YYYY</span></div></label>`+
 `<label class="guest-date-field"><span>Created date to</span><div class="guest-date-input-wrap"><input id="guest-date-to" class="guest-date-input${dateTo?"":" guest-date-empty"}" type="date" max="${dateNow()}" value="${esc(dateTo)}" aria-label="Guest created date to"><span class="guest-date-placeholder" aria-hidden="true">DD-MM-YYYY</span></div></label>`+
 `<button id="guest-search-btn" class="guest-filter-action">Search</button>`+
 `<button id="guest-clear-btn" class="guest-filter-action guest-clear-action">Clear</button>`+
 `</div>`+
 `<div class="card"><div class="page-head"><div><h3>Guest List</h3><span class="section-note">${rows.length} hotel guest(s)</span></div></div>${table(rows,actions)}</div>`;
}
async function guestDetail(customerId){
 const r=(await api(`/customers/${encodeURIComponent(customerId)}`)).data||{}, c=r.customer||{};
 const profile={
   "Customer ID":c.customer_id||"—",
   "Guest Name":c.customer_name||"—",
   "Mobile":c.customer_mobile||"—",
   "Email":c.customer_email||"—",
   "Address":c.customer_address||"—",
   "City":c.customer_city||"—",
   "State":c.customer_state||"—",
   "Country":c.customer_country||"—",
   "Pincode":c.customer_pincode||"—",
   "Status":c.guest_status||"—",
   "Preferences":c.preferences||"—",
   "Special Requests":c.special_requests||"—",
   "Notes":c.guest_notes||"—",
   "Created Time":c.created_time||"—"
 };
 return pageHead(`Guest: ${c.customer_name||c.customer_id||"Guest"}`,`Customer ID ${c.customer_id||"—"}`,`<button data-back-guests>Back to Guests</button>`)+
 `<div class="grid guest-kpi-grid">${metric("Total Stays",r.stay_summary?.total_stays||0,"Completed stays")}${metric("Total Bookings",r.booking_summary?.total_bookings||0,"Room reservations")}${metric("Restaurant Orders",r.restaurant_summary?.total_orders||0,"Non-cancelled orders")}${metric("Total Spend",money(Number(r.stay_summary?.total_spend||0)+Number(r.restaurant_summary?.total_spend||0)),"Room + restaurant")}${metric("Lifecycle",r.lifecycle?.lifecycle_stage||r.lifecycle?.stage||"—","Guest lifecycle")}</div>`+
 `<div class="card guest-status-card" style="margin-top:14px;display:flex;align-items:center;justify-content:space-between;gap:16px;flex-wrap:wrap"><div class="guest-status-copy"><strong>Guest Status</strong><span class="section-note">Manage this guest from the Guest View.</span></div><div class="guest-status-actions" style="display:flex;align-items:center;gap:8px;flex-wrap:wrap"><span class="pill ${String(c.guest_status||"Active").toLowerCase()==="active"?"success":String(c.guest_status||"Active").toLowerCase()==="blacklisted"?"danger":"warning"}">${esc(c.guest_status||"Active")}</span>${c.guest_status==="Active"?`<button type="button" data-guest-status-action="Inactive" data-customer-id="${esc(c.customer_id||customerId)}">Deactivate</button><button type="button" data-guest-status-action="Blacklisted" data-customer-id="${esc(c.customer_id||customerId)}">Blacklist</button>`:c.guest_status==="Inactive"?`<button type="button" data-guest-status-action="Active" data-customer-id="${esc(c.customer_id||customerId)}">Activate</button><button type="button" data-guest-status-action="Blacklisted" data-customer-id="${esc(c.customer_id||customerId)}">Blacklist</button>`:`<button type="button" data-guest-status-action="Active" data-customer-id="${esc(c.customer_id||customerId)}">Activate</button>`}</div></div>`+
 `<div class="guest-detail-sections" role="tablist" aria-label="Guest detail sections">`+
 `<button type="button" class="card guest-detail-tab" data-guest-section="profile" aria-expanded="false"><strong>Guest Profile</strong><span>Personal details</span></button>`+
 `<button type="button" class="card guest-detail-tab" data-guest-section="relationship" aria-expanded="false"><strong>Hotel Relationship</strong><span>Hotel-linked details</span></button>`+
 `<button type="button" class="card guest-detail-tab" data-guest-section="booking" aria-expanded="false"><strong>Booking History</strong><span>Reservation records</span></button>`+
 `<button type="button" class="card guest-detail-tab" data-guest-section="orders" aria-expanded="false"><strong>Order History</strong><span>Restaurant orders</span></button>`+
 `<button type="button" class="card guest-detail-tab" data-guest-section="feedback" aria-expanded="false"><strong>Feedback History</strong><span>Guest feedback</span></button>`+
 `</div>`+
 `<div class="guest-detail-panels">`+
 `<section data-guest-panel="profile" hidden class="card guest-detail-panel"><div class="page-head"><div><h3>Guest Profile</h3><span class="section-note">Personal details</span></div><button type="button" data-edit-current="${esc(c.customer_id||customerId)}">Edit Profile</button></div>${table([profile])}</section>`+
 `<section data-guest-panel="relationship" hidden class="card guest-detail-panel"><h3>Hotel Relationship</h3>${table(r.hotel_relationships||[])}</section>`+
 `<section data-guest-panel="booking" hidden class="card guest-detail-panel"><h3>Booking History</h3>${table(r.booking_history||[])}</section>`+
 `<section data-guest-panel="orders" hidden class="card guest-detail-panel"><h3>Order History</h3>${table(r.order_history||[])}</section>`+
 `<section data-guest-panel="feedback" hidden class="card guest-detail-panel"><h3>Feedback History</h3>${table(r.feedback_history||[])}</section>`+
 `</div>`;
}
async function rooms(){
  const status=String(state.roomStatus||"");
  const date=state.roomAvailabilityDate||dateNow();
  const nights=Number(state.roomAvailabilityNights||1);
  const roomSection=state.roomSection||"overview";
  const reservationSearch=String(state.roomReservationSearch||"").trim().toLowerCase();
  const reservationSearchField=String(state.roomReservationSearchField||"all");
  const reservationDateFrom=String(state.roomReservationDateFrom||"");
  const reservationDateTo=String(state.roomReservationDateTo||"");
  const roomActiveQuery="?active_only=true";
  const bookingQuery=status?`?status=${encodeURIComponent(status)}`:"";

  const [r,a,avail,financial]=await Promise.all([
    api(`/rooms${roomActiveQuery}`),
    api("/room-bookings"+bookingQuery+(bookingQuery?"&":"?")+"include_folio_totals=true"),
    api(`/rooms/availability?check_in_date=${encodeURIComponent(date)}&nights=${nights}`),
    api(`/rooms/financial-summary?business_date=${encodeURIComponent(dateNow())}`)
  ]);

  const roomsRows=Array.isArray(r.data)?r.data:[];
  const reservationRows=Array.isArray(a.data)?a.data:[];
  const availabilityRows=Array.isArray(avail.data)?avail.data:[];
  const roomFinancial=financial.data||{};
  const selectedDate=String(date||"").slice(0,10);
  const today=dateNow();
  const currentStayStarted=selectedDate && today && selectedDate<=today;
  const visibleAvailability=currentStayStarted
    ? availabilityRows.filter(x=>!["Occupied","Dirty","Cleaning","Maintenance","Out of Service"].includes(String(x.room_status||"")))
    : availabilityRows;

  const parseRoomDate=value=>{
    const text=String(value||"").trim();
    if(!text)return null;
    const ddmmyyyy=text.match(/^(\d{2})[-\/]?(\d{2})[-\/](\d{4})/);
    if(ddmmyyyy)return `${ddmmyyyy[3]}-${ddmmyyyy[2]}-${ddmmyyyy[1]}`;
    const iso=text.match(/^(\d{4})-(\d{2})-(\d{2})/);
    if(iso)return `${iso[1]}-${iso[2]}-${iso[3]}`;
    return null;
  };
  const selectedDateIso=parseRoomDate(date);
  const todayIso=dateNow();
  const addDays=(iso,days)=>{
    const d=new Date(`${iso}T00:00:00`);
    d.setDate(d.getDate()+days);
    return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,"0")}-${String(d.getDate()).padStart(2,"0")}`;
  };
  const tomorrowIso=addDays(todayIso,1);
  const reservationRowsVisible=reservationRows.filter(row=>{
    const bookingDate=parseRoomDate(row.booking_date||row.check_in_date||row.created_at);
    const searchFields={id:String(row.booking_id||""),name:String(row.customer_name||""),mobile:String(row.customer_mobile||""),room:String(row.room_number||""),type:String(row.room_type||"")};
    const searchText=reservationSearchField==="all" ? Object.values(searchFields).join(" ").toLowerCase() : String(searchFields[reservationSearchField]||"").toLowerCase();
    if(reservationSearch && !searchText.includes(reservationSearch))return false;
    if(reservationDateFrom && (!bookingDate || bookingDate<reservationDateFrom))return false;
    if(reservationDateTo && (!bookingDate || bookingDate>reservationDateTo))return false;
    return true;
  });

  // Front-page room status counts intentionally stay summary-only.
  // Housekeeping operations remain in the separate Housekeeping module.
  const occupiedCount=roomsRows.filter(x=>String(x.room_status||"").toLowerCase()==="occupied").length;
  const bookedStatuses=["Pending","Confirmed"];
  const todayBookedRows=reservationRows.filter(row=>{
    const bookingStatus=String(row.booking_status||"");
    if(!bookedStatuses.includes(bookingStatus))return false;
    return parseRoomDate(row.check_in_date)===todayIso;
  });
  const pendingCheckinRows=reservationRows.filter(row=>{
    const bookingStatus=String(row.booking_status||"");
    const start=parseRoomDate(row.check_in_date);
    return bookedStatuses.includes(bookingStatus) && !!start && start<todayIso;
  });
  const todayCheckinRows=todayBookedRows;
  const activeCheckoutStatuses=["checked-in","checked in","occupied"];
  const excludedCheckoutStatuses=["cancelled","no-show","checked-out","checked_out"];
  const todayCheckoutRows=reservationRows.filter(row=>{
    const bookingStatus=String(row.booking_status||"").toLowerCase();
    if(excludedCheckoutStatuses.includes(bookingStatus))return false;
    return parseRoomDate(row.expected_check_out)===todayIso;
  });
  const pendingCheckoutRows=reservationRows.filter(row=>{
    const bookingStatus=String(row.booking_status||"").toLowerCase();
    const expectedOut=parseRoomDate(row.expected_check_out);
    return activeCheckoutStatuses.includes(bookingStatus) && !!expectedOut && expectedOut<todayIso;
  });
  const futureBookingRows=reservationRows.filter(row=>{
    const bookingStatus=String(row.booking_status||"");
    if(!bookedStatuses.includes(bookingStatus))return false;
    const start=parseRoomDate(row.check_in_date);
    return !!start && start>todayIso;
  });
  const bookedRoomRows=reservationRows.filter(row=>{
    const bookingStatus=String(row.booking_status||"");
    if(!bookedStatuses.includes(bookingStatus))return false;
    const start=parseRoomDate(row.check_in_date);
    const end=parseRoomDate(row.expected_check_out);
    if(!selectedDateIso)return true;
    return start && (!end || (selectedDateIso>=start && selectedDateIso<end));
  });
  const housekeepingCount=roomsRows.filter(x=>{
    const roomStatus=String(x.room_status||"");
    const hkStatus=String(x.housekeeping_status||"");
    return ["Dirty","Cleaning"].includes(roomStatus) || ["Pending","In Progress","Cleaning"].includes(hkStatus);
  }).length;

  const roomActions=(row)=>{
    const statusValue=String(row?.room_status||"");
    const statusAction=isActionAllowed("room_status") && !["Dirty","Cleaning"].includes(statusValue)
      ? ` <button data-room-status="{{i}}">Status</button>` : "";
    return `<button data-room-detail="{{i}}">Details</button>${isActionAllowed("room_update")?` <button data-room-edit="{{i}}">Edit</button>`:""}${statusAction}`;
  };
  const bookingActions=(row)=>`<button data-reservation-detail-id="${esc(row.booking_id||"")}">View</button>`;

  const roomTable=(title,subtitle,body,actions="")=>`
    <div class="room-subpage">
      <div class="room-subpage-head"><div><h2>${esc(title)}</h2><p>${esc(subtitle)}</p></div><div class="room-subpage-actions">${actions}<button data-room-home>Back to Overview</button></div></div>
      ${body}
    </div>`;

  if(roomSection==="rooms"){
    return roomTable("Room Master","Manage rooms and room details.",table(roomsRows,roomActions),isActionAllowed("room_create")?`<button class="primary" data-action="room_create">+ Add Room</button>`:"");
  }
  if(roomSection==="available"){
    const body=`<div class="card room-section-card"><div class="toolbar room-filter-bar"><input id="room-avail-date" type="date" value="${esc(date)}"><input id="room-avail-nights" type="number" min="1" max="365" value="${nights}" aria-label="Number of nights"><button id="room-avail-btn" class="primary">Check Availability</button></div>${table(visibleAvailability)}</div>`;
    return roomTable("Available Rooms","Rooms available for the selected check-in date and stay length.",body);
  }
  if(roomSection==="occupied"){
    const occupiedRows=roomsRows.filter(row=>String(row.room_status||"").toLowerCase()==="occupied");
    const hotelProfile=(await api("/hotel/profile")).data||{};
    const occupiedReservations=reservationRows
      .filter(row=>["checked-in","checked in","occupied"].includes(String(row.booking_status||"").trim().toLowerCase()))
      .sort((a,b)=>String(b.created_at||"").localeCompare(String(a.created_at||"")));
    const occupiedStayByRoom=new Map();
    occupiedReservations.forEach(row=>{
      const roomNumber=String(row.room_number||"").trim();
      if(roomNumber && !occupiedStayByRoom.has(roomNumber)) occupiedStayByRoom.set(roomNumber,row);
    });
    const paymentStatus=(stay)=>{
      const paid=Number(stay?.paid_amount||0);
      const total=Number(stay?.grand_total||stay?.total_amount||0);
      if(stay?.payment_status && /paid|complete|settled/i.test(String(stay.payment_status))) return "Complete";
      return total>0 && paid>=total ? "Complete" : "Pending";
    };
    const occupiedBody=occupiedRows.length
      ? `<div class="card room-section-card">
          <div class="table-wrap occupied-rooms-table-wrap">
            <table class="data-table occupied-rooms-table">
              <thead>
                <tr>
                  <th>Room No.</th>
                  <th>Guest Name</th>
                  <th>Mobile No.</th>
                  <th>Floor</th>
                  <th>Capacity</th>
                  <th>Check-in</th>
                  <th>Check-out</th>
                  <th>Status</th>
                  <th>Payment</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                ${occupiedRows.map((room)=>{
                  const stay=occupiedStayByRoom.get(String(room.room_number||"").trim())||{};
                  const bookingId=stay.booking_id||"";
                  const payment=paymentStatus(stay);
                  const actualCheckIn=String(stay.actual_check_in||"").trim();
                  const checkInTime=actualCheckIn ? (()=>{ const d=new Date(actualCheckIn.replace(" ","T").replace(/([+-]\d{2}:?\d{2}|Z)$/,"")); return Number.isNaN(d.getTime()) ? actualCheckIn : d.toLocaleTimeString("en-IN",{hour:"2-digit",minute:"2-digit",hour12:true}); })() : (stay.early_check_in_time||hotelProfile.hotel_checkin_time||"—");
                  const checkOutTime=stay.late_check_out_time || hotelProfile.hotel_checkout_time || "—";
                  const formatStayDate=value=>{
                    const text=String(value||"").trim();
                    if(!text)return "—";
                    const match=text.match(/^(\d{2})[-\/]?(\d{2})[-\/](\d{4})/);
                    if(match){
                      const months=["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
                      return `${match[1]} ${months[Number(match[2])-1]||match[2]} ${match[3]}`;
                    }
                    const iso=text.match(/^(\d{4})-(\d{2})-(\d{2})/);
                    if(iso){
                      const months=["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
                      return `${iso[3]} ${months[Number(iso[2])-1]||iso[2]} ${iso[1]}`;
                    }
                    return text.split("T")[0].split(" ")[0] || "—";
                  };
                  const checkInDate=formatStayDate(actualCheckIn||stay.check_in_date);
                  const checkOutDate=formatStayDate(stay.expected_check_out||stay.check_out_date);
                  const viewButton=bookingId ? `<button type="button" data-reservation-detail-id="${esc(bookingId)}">View</button>` : `<button type="button" data-occupied-room-view="${esc(room.room_number||"")}">View</button>`;
                  return `<tr>
                    <td><strong>${esc(room.room_number||"—")}</strong></td>
                    <td>${esc(stay.customer_name||"—")}</td>
                    <td>${esc(stay.customer_mobile||"—")}</td>
                    <td>${esc(room.floor??"—")}</td>
                    <td>${esc(room.capacity??"—")}</td>
                    <td><div class="stay-date-time"><strong>${esc(checkInDate)}</strong><span>${esc(checkInTime)}</span></div></td>
                    <td><div class="stay-date-time"><strong>${esc(checkOutDate)}</strong><span>${esc(checkOutTime)}</span></div></td>
                    <td><span class="status-pill occupied-room-status">Occupied</span></td>
                    <td><span class="status-pill ${payment==="Complete"?"success":"warning"}">${payment}</span></td>
                    <td>
                      <details class="occupied-room-actions">
                        <summary>Action</summary>
                        <div class="occupied-room-action-menu">
                          ${bookingId && isActionAllowed("room_status") ? `<button type="button" data-occupied-action="check-out" data-booking-id="${esc(bookingId)}">Check-out</button>` : ""}
                          ${bookingId && isActionAllowed("room_status") ? `<button type="button" data-occupied-action="late-check-out" data-booking-id="${esc(bookingId)}">Late Check-out</button>` : ""}
                          ${bookingId && isActionAllowed("room_status") ? `<button type="button" data-occupied-action="transfer-room" data-booking-id="${esc(bookingId)}">Transfer Room</button>` : ""}
                          ${bookingId ? `<button type="button" data-occupied-action="guest-service" data-booking-id="${esc(bookingId)}">Guest Service</button>` : ""}
                          ${isActionAllowed("room_update") ? `<button type="button" data-occupied-action="need-housekeeping" data-room-number="${esc(room.room_number||"")}">Need Housekeeping</button>` : ""}
                          ${isActionAllowed("room_update") ? `<button type="button" data-occupied-action="maintenance" data-room-number="${esc(room.room_number||"")}">Maintenance</button>` : ""}
                        </div>
                      </details>
                      <div class="occupied-room-view">${viewButton}</div>
                    </td>
                  </tr>`;
                }).join("")}
              </tbody>
            </table>
          </div>
        </div>`
      : `<div class="card room-section-card"><div class="empty-state">No rooms are currently occupied.</div></div>`;
    return roomTable("Occupied Rooms","Rooms currently checked in and in use.",occupiedBody);
  }
  if(roomSection==="housekeeping"){
    const housekeepingRows=roomsRows.filter(row=>{
      const roomStatus=String(row.room_status||"");
      const hkStatus=String(row.housekeeping_status||"");
      return ["Dirty","Cleaning"].includes(roomStatus) || ["Pending","In Progress","Cleaning"].includes(hkStatus);
    });
    const body=`<div class="card room-section-card">${housekeepingRows.length ? table(housekeepingRows) : `<div class="empty-state">No rooms are currently pending housekeeping.</div>`}</div>`;
    return roomTable("Housekeeping Summary","Rooms awaiting cleaning are shown here. Cleaning operations remain in the separate Housekeeping module.",body);
  }
  if(roomSection==="future"){
    const futureBody=futureBookingRows.length
      ? `<div class="card room-section-card"><div class="table-wrap"><table class="data-table booked-rooms-table"><thead><tr><th>Room</th><th>Guest</th><th>Check-in</th><th>Expected Check-out</th><th>Status</th><th>Grand Total</th><th>View</th></tr></thead><tbody>${futureBookingRows.map(row=>`<tr><td>${esc(row.room_number||"—")}</td><td><strong>${esc(row.customer_name||"—")}</strong><div class="section-note">${esc(row.customer_mobile||"")}</div></td><td>${esc(row.check_in_date||"—")}</td><td>${esc(row.expected_check_out||"—")}</td><td>${esc(row.booking_status||"—")}</td><td>${money(row.grand_total||0)}</td><td><button type="button" data-reservation-detail-id="${esc(row.booking_id||"")}">View</button></td></tr>`).join("")}</tbody></table></div></div>`
      : `<div class="card room-section-card"><div class="empty-state">No future bookings.</div></div>`;
    return roomTable("Future Bookings","Reservations with a check-in date after today.",futureBody);
  }
  if(roomSection==="booked"){
    const bookedBody=todayBookedRows.length
      ? `<div class="card room-section-card"><div class="table-wrap"><table class="data-table booked-rooms-table"><thead><tr><th>Room</th><th>Guest</th><th>Check-in</th><th>Expected Check-out</th><th>Status</th><th>Grand Total</th><th>Actions</th></tr></thead><tbody>${todayBookedRows.map(row=>`<tr><td>${esc(row.room_number||"—")}</td><td><strong>${esc(row.customer_name||"—")}</strong><div class="section-note">${esc(row.customer_mobile||"")}</div></td><td>${esc(row.check_in_date||"—")}</td><td>${esc(row.expected_check_out||"—")}</td><td>${esc(row.booking_status||"—")}</td><td>${money(row.grand_total||0)}</td><td><div class="room-row-actions"><button type="button" data-booked-room-action="${esc(row.booking_id||"")}">Action</button><button type="button" data-reservation-detail-id="${esc(row.booking_id||"")}">View</button></div></td></tr>`).join("")}</tbody></table></div></div>`
      : `<div class="card room-section-card"><div class="empty-state">No bookings for today.</div></div>`;
    return roomTable("Today Booked","Confirmed/pending reservations whose stay includes today and are awaiting check-in.",bookedBody);
  }
  if(roomSection==="pending-movements" || roomSection==="pending-checkin" || roomSection==="today-checkout" || roomSection==="pending-checkout"){
    const isCombined=roomSection==="pending-movements";
    const isPendingIn=roomSection==="pending-checkin";
    const isTodayOut=roomSection==="today-checkout";
    const sourceRows=isCombined
      ? [...pendingCheckinRows.map(row=>({...row,pending_type:"Pending Check-in"})),...pendingCheckoutRows.map(row=>({...row,pending_type:"Pending Check-out"}))]
      : (isPendingIn?pendingCheckinRows:(isTodayOut?todayCheckoutRows:pendingCheckoutRows));
    const title=isCombined?"Pending Arrivals & Departures":(isPendingIn?"Pending Check-in":(isTodayOut?"Today Check-out":"Pending Check-out"));
    const description=isCombined
      ? "Past-due arrivals that have not checked in and departures whose checkout is still pending."
      : (isPendingIn?"Reservations with a past check-in date that have not checked in yet.":(isTodayOut?"Guests whose expected check-out date is today.":"Guests whose expected check-out date has passed but checkout is not complete."));
    const body=sourceRows.length
      ? `<div class="card room-section-card"><div class="table-wrap"><table class="data-table booked-rooms-table"><thead><tr>${isCombined?"<th>Pending Type</th>":""}<th>Room</th><th>Guest</th><th>Booking ID</th><th>Booking Date &amp; Time</th><th>Check-in</th><th>Expected Check-out</th><th>Status</th><th>Grand Total</th><th>Outstanding</th><th>Actions</th></tr></thead><tbody>${sourceRows.map(row=>`<tr>${isCombined?`<td><strong>${esc(row.pending_type||"—")}</strong></td>`:""}<td>${esc(row.room_number||"—")}</td><td><strong>${esc(row.customer_name||"—")}</strong><div class="section-note">${esc(row.customer_mobile||"")}</div></td><td>${esc(row.booking_id||"—")}</td><td>${esc([row.booking_created_date||row.booking_date||"",row.booking_created_time||row.booking_time||""].filter(Boolean).join(" · ")||"—")}</td><td>${esc(row.check_in_date||"—")}</td><td>${esc(row.expected_check_out||"—")}</td><td>${esc(row.booking_status||"—")}</td><td>${money(row.folio_grand_total??row.grand_total??0)}</td><td>${money(row.folio_outstanding_amount??row.balance_amount??0)}</td><td><div class="room-row-actions"><button type="button" data-reservation-detail-id="${esc(row.booking_id||"")}">View</button>${(isPendingIn || (isCombined && row.pending_type==="Pending Check-in"))?`<button type="button" data-booked-room-action="${esc(row.booking_id||"")}">Action</button>`:""}</div></td></tr>`).join("")}</tbody></table></div></div>`
      : `<div class="card room-section-card"><div class="empty-state">No pending arrivals or departures.</div></div>`;
    return roomTable(title,description,body);
  }

  if(roomSection==="reservations"){
    const body=`<div class="card room-section-card">
      <div class="guest-filter-bar reservation-filter-bar" aria-label="Reservation search filters">
        <div class="guest-filter-control guest-search-control"><input class="search" id="room-reservation-search" type="search" placeholder="Search booking ID, guest, mobile or room…" value="${esc(state.roomReservationSearch||"")}" aria-label="Search reservations"></div>
        <div class="guest-filter-control"><select id="room-reservation-search-field" aria-label="Search field"><option value="all" ${reservationSearchField==="all"?"selected":""}>All fields</option><option value="id" ${reservationSearchField==="id"?"selected":""}>Booking ID</option><option value="name" ${reservationSearchField==="name"?"selected":""}>Guest Name</option><option value="mobile" ${reservationSearchField==="mobile"?"selected":""}>Mobile</option><option value="room" ${reservationSearchField==="room"?"selected":""}>Room Number</option><option value="type" ${reservationSearchField==="type"?"selected":""}>Room Type</option></select></div>
        <div class="guest-filter-control"><select id="room-status-filter" aria-label="Reservation status"><option value="">All statuses</option>${["Pending","Confirmed","Checked-In","Checked-Out","Cancelled","No-Show"].map(x=>`<option value="${esc(x)}" ${status===x?"selected":""}>${esc(x)}</option>`).join("")}</select></div>
        <label class="guest-date-field"><span>Booking from</span><div class="guest-date-input-wrap"><input id="room-reservation-date-from" class="guest-date-input${reservationDateFrom?"":" guest-date-empty"}" type="date" value="${esc(reservationDateFrom)}" aria-label="Reservation booking date from"><span class="guest-date-placeholder" aria-hidden="true">DD-MM-YYYY</span></div></label>
        <label class="guest-date-field"><span>Booking to</span><div class="guest-date-input-wrap"><input id="room-reservation-date-to" class="guest-date-input${reservationDateTo?"":" guest-date-empty"}" type="date" value="${esc(reservationDateTo)}" aria-label="Reservation booking date to"><span class="guest-date-placeholder" aria-hidden="true">DD-MM-YYYY</span></div></label>
        <button id="room-reservation-search-btn" class="guest-filter-action">Search</button>
        <button id="room-status-clear" class="guest-filter-action guest-clear-action">Clear</button>
      </div>
      <div class="section-note" style="margin:10px 0">${reservationRowsVisible.length} reservation${reservationRowsVisible.length===1?"":"s"} found</div>
      ${reservationRowsVisible.length ? table(reservationRowsVisible,bookingActions) : `<div class="empty-state">No reservations match the selected filters.</div>`}
    </div>`;
    return roomTable("Reservations","Search, review and manage reservation history.",body);
  }

  const now=new Date();
  const dateLabel=now.toLocaleDateString("en-GB",{day:"2-digit",month:"short",year:"numeric"});
  const dayLabel=now.toLocaleDateString("en-US",{weekday:"long"});
  const userName=String(state.user?.username||"admin");
  const userInitial=(userName[0]||"A").toUpperCase();
  const notificationCount=String(document.getElementById("notification-count")?.textContent||"").trim();
  const totalSales=Number(roomFinancial.room_sales||0);
  const todaySales=Number(roomFinancial.today_room_revenue||0);
  const totalOutstanding=Number(roomFinancial.room_outstanding||0);
  let guestIssueCount=0;
  try{
    const issueResponse=await api("/feedback?complaint_only=true&limit=1000");
    const issueRows=Array.isArray(issueResponse.data)?issueResponse.data:[];
    guestIssueCount=issueRows.filter(row=>!["Resolved","Closed"].includes(String(row.status||""))).length;
  }catch(e){
    guestIssueCount=0;
  }

  const summaryCard=(tone,icon,label,sub,value,extra="",wrap=true)=>`
    ${wrap?`<article class="room-summary-card room-tone-${tone}">`:""}
      <div class="room-card-top"><div class="room-card-icon">${icon}</div><div><h3>${esc(label)}</h3><p>${esc(sub)}</p></div></div>
      <div class="room-card-value">${esc(money(value))}</div>
      <div class="room-card-foot"><span class="room-live-dot"></span><span>${esc(extra)}</span><span class="room-spark room-spark-${tone}" aria-hidden="true"><i></i><i></i><i></i><i></i><i></i></span></div>
    ${wrap?"</article>":""}`;

  const statusCard=(tone,icon,label,value,sub,section)=>{
    const pageTarget=["frontdesk","feedback"].includes(section||"") ? `data-page="${esc(section)}"` : `data-room-section="${esc(section||"")}"`;
    return `<article class="room-status-card room-status-${tone}" ${pageTarget} role="button" tabindex="0" aria-label="Open ${esc(label)} details">
      <div class="room-status-icon">${icon}</div><div class="room-status-content"><h3>${esc(label)}</h3><strong>${esc(String(value))}</strong><p>${esc(sub)}</p></div>
    </article>`;
  };

  return `<div class="room-page">
    <section class="room-hero">
      <div class="room-hero-shade"></div>
      <div class="room-hero-content">
        <div class="room-hero-title"><div class="room-hero-logo">▣</div><div><h1>Rooms &amp; Reservations</h1><p>Room master, availability, reservations and room revenue</p></div></div>
        <div class="room-hero-tools">
          <div class="room-date-chip"><span>▣</span><div><strong>${esc(dateLabel)}</strong><small>${esc(dayLabel)}</small></div></div>
          <button class="room-notify-chip" type="button" data-room-notifications aria-label="Open notifications"><span>♧</span>${notificationCount&&notificationCount!=="0"?`<b>${esc(notificationCount)}</b>`:""}</button>
          <div class="room-user-stack">
            <button class="room-user-chip" type="button" data-room-profile><span class="room-avatar">${esc(userInitial)}</span><strong>${esc(userName)}</strong><span>⌄</span></button>
            ${isActionAllowed("booking")?`<button class="room-reservation-quick" type="button" data-action="booking">＋ Reservation</button>`:""}
          </div>
        </div>
      </div>
      <button class="room-hero-back" type="button" data-room-exit>← Back to Dashboard</button>

      <div class="room-dashboard-content">
        <div class="room-revenue-row">
          <article class="room-summary-card room-tone-sales" data-room-financial="sales" role="button" tabindex="0" aria-label="Open Total Sales details">${summaryCard("sales","▤","Total Sales","Total received amount (till now)",totalSales,"All recorded room payments",false)}</article>
          <article class="room-summary-card room-tone-today" data-room-financial="today" role="button" tabindex="0" aria-label="Open Today Sales details">${summaryCard("today","▣","Today Sales","Today's received amount",todaySales,`${roomFinancial.today_room_payments||0} payment transaction(s) today`,false)}</article>
          <article class="room-summary-card room-tone-outstanding" data-room-financial="outstanding" role="button" tabindex="0" aria-label="Open Total Outstanding details">${summaryCard("outstanding","▰","Total Outstanding","Pending amount (not yet received)",totalOutstanding,"Current unpaid room balance",false)}</article>
          <button class="room-check-card" type="button" data-room-section="reservations"><span class="room-check-icon">▤</span><strong>Check<br>Reservation</strong><span class="room-arrow">→</span></button>
        </div>
        <div class="room-operations-row" aria-label="Today's operations">
          ${statusCard("today-checkin","✓","Today Check-in",todayCheckinRows.length,"Arrivals awaiting check-in","booked")}
          ${statusCard("today-checkout","↗","Today Check-out",todayCheckoutRows.length,"Guests due to check out today","today-checkout")}
          ${statusCard("pending-movements","!","Pending Arrivals & Departures",pendingCheckinRows.length+pendingCheckoutRows.length,`Check-in: ${pendingCheckinRows.length} · Check-out: ${pendingCheckoutRows.length}`,"pending-movements")}
          ${statusCard("guest-issues","⚠","Guest Issues",guestIssueCount,"Open guest complaints/issues","feedback")}
        </div>
        <div class="room-status-row">
          ${statusCard("rooms","▦","Total Rooms",roomsRows.length,"Active rooms","rooms")}
          ${statusCard("available","▯","Available Rooms",visibleAvailability.length,"Ready to book","available")}
          ${statusCard("future","▣","Future Bookings",futureBookingRows.length,"Upcoming reservations","future")}
          ${statusCard("booked","▣","Today Booked",todayBookedRows.length,"Today's arrivals awaiting check-in","booked")}
          ${statusCard("occupied","●","Occupied Rooms",occupiedCount,"Currently checked-in","occupied")}
          ${statusCard("housekeeping","✦","Housekeeping",housekeepingCount,"Pending cleaning","housekeeping")}
        </div>
      </div>
    </section>
  </div>`;
}

async function reservationDetail(bookingId){
  window.__lastReservationBookingId=bookingId;
  const r=await api(`/room-bookings?booking_id=${encodeURIComponent(bookingId)}`);
  const b=r.data||{};
  let guestServices=[];
  try{ guestServices=(await api(`/guest-services/requests?booking_id=${encodeURIComponent(bookingId)}`)).data||[]; }catch(e){ guestServices=[]; }
  let customerProfile={};
  if(b.customer_id){
    try{ customerProfile=(await api(`/customers/${encodeURIComponent(b.customer_id)}`)).data?.customer||{}; }catch(e){ customerProfile={}; }
  }
  let folio={};
  try{ folio=(await api(`/room-payments/${encodeURIComponent(bookingId)}/folio`)).data?.folio||{}; }catch(e){ folio={}; }

  if(!b.booking_id){
    throw new Error("Reservation data was not returned by the server.");
  }

  const allocationRows=
    Array.isArray(r.rooms) && r.rooms.length
      ? r.rooms
      : [{
          room_number:b.room_number||"—",
          room_type:b.room_type||"—",
          room_status:b.booking_status||"—",
          check_in_date:b.check_in_date||"—",
          expected_check_out:b.expected_check_out||b.check_out_date||"—"
        }];

  const status=String(b.booking_status||"");
  const canModify=["Pending","Confirmed"].includes(status);
  const statusClass=status==="Checked-Out"||status==="Checked-In"?"success":status==="Cancelled"||status==="No-Show"?"danger":"warning";
  const roomTotal=Number(folio.room_total ?? b.grand_total ?? b.total_amount ?? 0);
  const serviceTotal=Number(folio.service_total ?? guestServices.filter(x=>x.billing_mode==="Reservation Bill").reduce((sum,x)=>sum+Number(x.price||0),0));
  const total=Number(folio.grand_total ?? (roomTotal+serviceTotal));
  const paid=Number(folio.paid_amount ?? b.paid_amount ?? 0);
  const balance=Number(folio.balance_amount ?? b.balance_amount ?? Math.max(0,total-paid));
  const roomCharges=Number(b.subtotal||b.room_subtotal||0);
  const gst=Number(b.gst||b.gst_amount||Math.max(0,roomTotal-roomCharges));

  const allocationHtml=allocationRows.map((row,index)=>`
    <div class="reservation-allocation-item">
      <div class="reservation-allocation-index">${index+1}</div>
      <div class="reservation-allocation-main">
        <strong>Room ${esc(row.room_number||"—")}</strong>
        <span>${esc(row.room_type||"Room")} ${row.room_price?`• ${money(row.room_price)}/night`:""}</span>
      </div>
      <div class="reservation-allocation-meta">
        <span>Check-in<strong>${esc(row.check_in_date||b.check_in_date||"—")}</strong></span>
        <span>Check-out<strong>${esc(row.expected_check_out||row.check_out_date||b.expected_check_out||b.check_out_date||"—")}</strong></span>
        <span>Status<strong>${esc(row.allocation_status||row.room_status||status||"—")}</strong></span>
      </div>
    </div>`).join("");

  const guestItems=[
    ["Guest Name",customerProfile.customer_name||b.customer_name],
    ["Mobile",customerProfile.customer_mobile||b.customer_mobile],
    ["Customer ID",customerProfile.customer_id||b.customer_id],
    ["Email",customerProfile.customer_email],
    ["Address",customerProfile.customer_address],
    ["City",customerProfile.customer_city],
    ["State",customerProfile.customer_state],
    ["Country",customerProfile.customer_country],
    ["Pincode",customerProfile.customer_pincode],
    ["Preferences",customerProfile.preferences],
    ["Special Requests",customerProfile.special_requests],
    ["Guest Notes",customerProfile.guest_notes||b.notes],
    ["Booking ID",b.booking_id],
    ["Booking Date",b.booking_date],
    ["Booking Time",b.booking_time]
  ].filter(x=>x[1]!==undefined&&x[1]!==null&&String(x[1])!=="");

  const stayItems=[
    ["Check-in",b.check_in_date],
    ["Check-out",b.expected_check_out||b.check_out_date],
    ["Actual Check-in",b.actual_check_in],
    ["Actual Check-out",b.actual_check_out],
    ["Nights",b.nights||b.days],
    ["Adults",b.adults],
    ["Children",b.children]
  ].filter(x=>x[1]!==undefined&&x[1]!==null&&String(x[1])!=="");

  const checkoutItems=[
    ["Checkout Type",b.checkout_type],
    ["Checkout Policy",b.checkout_policy],
    ["Actual Stay Nights",b.actual_stay_nights],
    ["Final Checkout Charge",b.checkout_final_charge!==undefined?money(b.checkout_final_charge):null],
    ["Adjustment / Refund",b.checkout_adjustment_amount!==undefined?money(b.checkout_adjustment_amount):null],
    ["Adjustment Type",b.checkout_adjustment_type],
    ["Checkout Note",b.checkout_notes]
  ].filter(x=>x[1]!==undefined&&x[1]!==null&&String(x[1])!=="");

  const detailList=(items)=>items.map(([label,value])=>`
    <div class="reservation-detail-item">
      <span>${esc(label)}</span>
      <strong>${esc(value)}</strong>
    </div>`).join("");

  const roomCards=allocationRows.map((row,index)=>`
    <div class="reservation-room-card">
      <div class="reservation-room-top">
        <div>
          <span class="reservation-room-number">Room ${esc(row.room_number||"—")}</span>
          <strong>${esc(row.room_type||"Room")}</strong>
        </div>
        <span class="reservation-status-badge ${statusClass}">${esc(row.allocation_status||row.room_status||status||"—")}</span>
      </div>
      <div class="reservation-room-meta">
        <div><span>Check-in</span><strong>${esc(row.check_in_date||b.check_in_date||"—")}</strong></div>
        <div><span>Check-out</span><strong>${esc(row.expected_check_out||row.check_out_date||b.expected_check_out||b.check_out_date||"—")}</strong></div>
      </div>
    </div>`).join("");

  return `<div class="reservation-detail-page">
    <div class="reservation-detail-head reservation-detail-header-card">
      <div class="reservation-detail-title">
        <button class="reservation-back-btn" data-back-rooms>← Back to Reservations</button>
        <div class="reservation-title-row">
          <div>
            <div class="reservation-eyebrow">RESERVATION</div>
            <h1>#${esc(b.booking_id||"")}</h1>
            <p>${esc(b.customer_name||"Guest")} <span>•</span> Room ${esc(b.room_number||"—")} <span>•</span> ${esc(b.room_type||"Standard")}</p>
          </div>
          <span class="reservation-status-badge large ${statusClass}">${esc(status||"—")}</span>
        </div>
      </div>
    </div>

    <div class="reservation-main-grid">
      <section class="card reservation-detail-card">
        <div class="reservation-card-head">
          <div>
            <h2>Guest & Reservation</h2>
            <p>Guest identity, booking reference and stay information.</p>
          </div>
        </div>
        <div class="reservation-info-sections">
          <div class="reservation-subsection reservation-info-section-wide">
            <h3>Guest & Booking</h3>
            <div class="reservation-detail-grid">${detailList(guestItems)}</div>
          </div>
          <div class="reservation-subsection">
            <h3>Stay</h3>
            <div class="reservation-detail-grid">${detailList(stayItems)}</div>
          </div>
          ${checkoutItems.length && (status==="Checked-Out" || b.checkout_type && b.checkout_type!=="Standard" || b.checkout_policy || b.actual_stay_nights || Number(b.checkout_final_charge||0)!==0 || Number(b.checkout_adjustment_amount||0)!==0 || b.checkout_adjustment_type || b.checkout_notes) ? `<div class="reservation-subsection">
            <h3>Checkout Information</h3>
            <div class="reservation-detail-grid">${detailList(checkoutItems)}</div>
          </div>` : ""}
      </section>

      <div class="reservation-side-stack">
        <section class="card reservation-detail-card reservation-room-allocation-card">
          <div class="reservation-card-head">
            <div>
              <h2>Room Allocation</h2>
              <p>Assigned room and stay dates.</p>
            </div>
          </div>
          <div class="reservation-room-list">${roomCards}</div>
        </section>

        <section class="card reservation-services-card reservation-inline-services-card">
          <div class="reservation-card-head">
            <div>
              <h2>Guest Services</h2>
              <p>Special requests and hotel services linked to this reservation.</p>
            </div>
          </div>
          ${guestServices.length ? `<div class="reservation-services-list">${guestServices.map(x=>`<div class="reservation-service-row"><div><strong>${esc(x.service_name||x.service_type||"Guest Service")}</strong><span>${esc(x.description||"")}</span><small>${x.required_at?`Required: ${esc(x.required_at)} · `:""}${x.price>0?money(x.price):"Free"} · ${esc(x.billing_mode||"Reservation Bill")} · ${esc(x.assigned_department||"Hotel Staff")}${x.payment_status&&x.price>0?` · Payment: ${esc(x.payment_status)}`:""}</small></div><div><span class="reservation-status-badge ${String(x.request_status||"")==="Completed"?"success":String(x.request_status||"")==="Cancelled"?"danger":"warning"}">${esc(x.request_status||"Requested")}</span>${x.billing_mode==="Separate Payment" && x.extra_charge_id && Number(x.price||0)>0 && x.payment_status!=="Paid" && isActionAllowed("room_payment_create") ? `<button type="button" data-guest-service-pay="${esc(x.extra_charge_id)}" data-booking-id="${esc(bookingId)}">Receive</button>` : ""}${isActionAllowed("room_status") && !["Completed","Cancelled"].includes(String(x.request_status||"")) ? `<button type="button" data-guest-service-status="${esc(x.request_id)}" data-next-status="${String(x.request_status||"")==="Requested"?"Acknowledged":String(x.request_status||"")==="Acknowledged"?"In Progress":"Completed"}">${String(x.request_status||"")==="In Progress"?"Mark Completed":"Update Status"}</button>`:""}</div></div>`).join("")}</div>` : `<div class="empty-state">No guest services added to this reservation.</div>`}
        </section>
      </div>
    </div>

    <section class="card reservation-financial-card">
      <div class="reservation-card-head">
        <div>
          <h2>Payment Summary</h2>
          <p>Reservation charges and current settlement position.</p>
        </div>
        <div class="reservation-financial-head-actions">
          <div class="reservation-financial-actions-row">
            ${balance>0.01 && isActionAllowed("room_payment_create") ? `<button
              class="reservation-receive-payment-btn"
              type="button"
              data-res-action="receive-payment"
              data-booking-id="${esc(b.booking_id)}"
            >+ Receive Payment</button>` : ""}
            <button
              class="reservation-payment-icon-btn"
              type="button"
              data-res-action="payment-history"
              data-booking-id="${esc(b.booking_id)}"
              title="View Payment History"
              aria-label="View Payment History"
            ><span aria-hidden="true">▤</span></button>
          </div>
          <span class="reservation-financial-status ${balance<=0.01?"settled":""}">${balance<=0.01?"Fully settled":"Balance due"}</span>
        </div>
      </div>
      <div class="reservation-financial-grid">
        <div><span>Room charges</span><strong>${money(roomCharges)}</strong></div>
        <div><span>GST</span><strong>${money(gst)}</strong></div>
        <div><span>Guest Services</span><strong>${money(serviceTotal)}</strong></div>
        <div><span>Grand Total</span><strong>${money(total)}</strong></div>
        <div><span>Paid</span><strong class="positive">${money(paid)}</strong></div>
        <div><span>Outstanding</span><strong class="${balance>0.01?"negative":"positive"}">${money(balance)}</strong></div>
      </div>
    </section>


    ${status==="Checked-Out" ? `<section class="card reservation-settlement-card">
      <div class="reservation-card-head">
        <div>
          <h2>Checkout Settlement</h2>
          <p>${esc(b.checkout_type==="Early" ? "Early check-out settlement recorded." : "Final checkout settlement recorded.")}</p>
        </div>
      </div>
      <div class="reservation-financial-grid">
        <div><span>Expected Check-out</span><strong>${esc(b.expected_check_out||b.check_out_date||"—")}</strong></div>
        <div><span>Actual Check-out</span><strong>${esc(b.actual_check_out||"—")}</strong></div>
        <div><span>Checkout Type</span><strong>${esc(b.checkout_type||"Standard")}</strong></div>
        <div><span>Final Charge</span><strong>${money(Number(b.checkout_final_charge ?? total))}</strong></div>
      </div>
    </section>` : ""}

  </div>`;
}

function restaurantTableStatusTable(rows){
  if(!Array.isArray(rows)||!rows.length)return `<div class="empty">No tables configured.</div>`;
  const keys=[...new Set(rows.flatMap(r=>Object.keys(r||{})))].slice(0,12);
  const canUpdate=isActionAllowed("table_status");
  const head=keys.map(k=>`<th>${esc(k.replaceAll("_"," "))}</th>`).join("")+(canUpdate?`<th>Actions</th>`:"");
  const body=rows.map((r,i)=>{
    const status=String(r.table_status||"");
    let actions="";
    if(canUpdate){
      if(status==="Available"){
        actions=`<button data-table-occupy="${i}">Mark Occupied</button>`;
      }else if(status==="Occupied"){
        actions=`<button data-table-release="${i}">Release Table</button>`;
      }
    }
    return `<tr>${keys.map(k=>`<td>${cell(r[k])}</td>`).join("")}${canUpdate?`<td>${actions||"—"}</td>`:""}</tr>`;
  }).join("");
  return `<div class="table-wrap"><table class="data-table"><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table></div>`;
}

function restaurantCompactTable(rows, columns, actions=""){
  if(!Array.isArray(rows)||!rows.length)return `<div class="empty">No records found.</div>`;
  const head=columns.map(c=>`<th>${esc(c.label)}</th>`).join("")+(actions?`<th>Actions</th>`:"");
  const body=rows.map((r,i)=>`<tr>${columns.map(c=>`<td>${cell(r[c.key])}</td>`).join("")}${actions?`<td>${actions.replaceAll("{{i}}",i)}</td>`:""}</tr>`).join("");
  return `<div class="restaurant-data-wrap"><table class="data-table restaurant-data-table"><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table></div>`;
}

function restaurantTableStatusCompact(rows){
  if(!Array.isArray(rows)||!rows.length)return `<div class="empty">No tables configured.</div>`;
  const columns=[
    {key:"table_number",label:"Table"},
    {key:"table_capacity",label:"Capacity"},
    {key:"table_status",label:"Status"},
    {key:"table_section",label:"Section"},
    {key:"is_active",label:"Active"}
  ];
  const canUpdate=isActionAllowed("table_status");
  const canCreate=isActionAllowed("table_create");
  const head=columns.map(c=>`<th>${esc(c.label)}</th>`).join("")+(canUpdate?`<th>Actions</th>`:"");
  const body=rows.map((r,i)=>{
    const status=String(r.table_status||"");
    const active=Number(r.is_active||0)===1;
    let action="";
    if(canUpdate){
      if(!active) action=`<button data-table-active="${i}">Activate</button>`;
      else if(status==="Available") action=`<button data-table-occupy="${i}">Mark Occupied</button> <button data-table-edit="${i}">Edit</button> <button data-table-active="${i}">Deactivate</button>`;
      else if(status==="Occupied") action=`<button data-table-release="${i}">Release Table</button>`;
      else if(status==="Cleaning Required") action=`<button data-table-clean-start="${i}">Start Cleaning</button>`;
      else if(status==="Cleaning In Progress") action=`<button data-table-clean-complete="${i}">Complete Cleaning</button>`;
    }
    return `<tr>${columns.map(c=>`<td>${c.key==="is_active"?(active?"Active":"Inactive"):cell(r[c.key])}</td>`).join("")}${canUpdate?`<td>${action||"—"}</td>`:""}</tr>`;
  }).join("");
  return `<div class="table-management-toolbar"><div class="section-note">Add, edit, or activate/deactivate restaurant tables. Active tables are available for POS use.</div>${canCreate?`<button class="primary" data-table-add>+ Add Table</button>`:""}</div><div class="restaurant-data-wrap"><table class="data-table restaurant-data-table"><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table></div>`;
}

async function restaurant(){
  const menuEndpoint=currentRole()==="kitchen"?"/restaurant/menu?available_only=false":"/restaurant/menu";
  const [dashboardData,categoriesData,menuData,allOrdersData]=await Promise.all([
    api("/restaurant/dashboard"),
    api("/restaurant/menu/categories"),
    api(menuEndpoint),
    api("/restaurant/orders")
  ]);
  const d=dashboardData.data||{};
  const categories=categoriesData.data||[];
  const menuFromEndpoint=Array.isArray(menuData.data)?menuData.data:[];
  const allRestaurantOrders=Array.isArray(allOrdersData.data)?allOrdersData.data:[];
  const totalSalesRevenue=allRestaurantOrders
    .filter(order=>String(order.order_status||"").toLowerCase()!=="cancelled")
    .reduce((sum,order)=>sum+Number(order.grand_total||0),0);
  const o=d.overview||{};
  const orders=d.orders||[], kitchen=d.kitchen_orders||[], menu=menuFromEndpoint, tables=d.tables||[], bookings=d.table_bookings||[];
  const activeTables=tables.filter(t=>Number(t.is_active||0)===1);
  const cleaningRequiredTables=Number(o.cleaning_required_tables||0);
  const cleaningInProgressTables=Number(o.cleaning_in_progress_tables||0);
  const statusOptions=["","New","Accepted","Preparing","Ready","Served","Completed","Cancelled"];
  const restaurantOrderDateFilter=String(state.restaurantOrderDateFilter||"all");
  const restaurantOrderCustomDate=String(state.restaurantOrderCustomDate||"");
  const restaurantSection=state.restaurantSection||"overview";
  window.__restaurantOrderRows=orders;
  window.__allRestaurantOrderRows=allRestaurantOrders;
  window.__restaurantKitchenRows=kitchen;
  window.__restaurantMenuRows=menu;
  window.__restaurantTableRows=tables;
  window.__restaurantMenuCategories=categories;
  const menuActions=isActionAllowed("restaurant_menu_update")
    ? '<button data-menu-edit="{{i}}">Edit</button> <button data-menu-availability="{{i}}">Toggle Availability</button>'
    : '';
  const orderActions=`<button data-restaurant-detail="{{i}}">Details</button>${isActionAllowed("order_status")?" <button data-restaurant-status=\"{{i}}\">Update Status</button>":""}`;
  const menuColumns=[
    {key:"item_id",label:"Item ID"},{key:"item_name",label:"Item Name"},{key:"category_name",label:"Category"},
    {key:"price",label:"Price"},{key:"is_available",label:"Available"}
  ];
  const kitchenColumns=[
    {key:"order_id",label:"Order ID"},{key:"order_date",label:"Order Date"},{key:"customer_name",label:"Guest"},
    {key:"table_number",label:"Table"},{key:"order_status",label:"Status"}
  ];
  const tableColumns=[
    {key:"table_number",label:"Table"},{key:"capacity",label:"Capacity"},{key:"table_status",label:"Status"},{key:"table_section",label:"Section"}
  ];
  const bookingColumns=[
    {key:"booking_id",label:"Booking ID"},{key:"guest_name",label:"Guest"},{key:"table_number",label:"Table"},
    {key:"booking_date",label:"Date"},{key:"status",label:"Status"}
  ];

  const restaurantTab=(section,label,badge="")=>roleAllowsRestaurantSection(section)?`<button type="button" class="room-tab ${restaurantSection===section?"active":""}" data-restaurant-section="${section}" role="tab" aria-selected="${restaurantSection===section}">${label}${badge?` <span>${badge}</span>`:""}</button>`:"";
  if(currentRole()==="kitchen"){
    const reqRes=await api("/kitchen/requests");
    const kitchenRequests=Array.isArray(reqRes.data)?reqRes.data:[];
    window.__kitchenRequestRows=kitchenRequests;
    const completedOrders=allRestaurantOrders.filter(r=>String(r.order_status||"") === "Completed");
    const todayDate=String(d.date||dateNow());
    const todayOrders=allRestaurantOrders.filter(r=>String(r.order_date||"")===todayDate);
    const completedToday=completedOrders.filter(r=>{
      const completedAt=String(r.completed_at||"").trim();
      if(completedAt) return completedAt.slice(0,10)===todayDate;
      return String(r.order_date||"")===todayDate;
    });
    const nonCancelled=allRestaurantOrders.filter(r=>String(r.order_status||"").toLowerCase()!=="cancelled");
    const liveKitchenOrders=allRestaurantOrders.filter(r=>["New","Accepted","Preparing","Ready"].includes(String(r.order_status||"New")));
    const newOrders=liveKitchenOrders.filter(r=>String(r.order_status||"New")==="New");
    const acceptedOrders=liveKitchenOrders.filter(r=>String(r.order_status||"")==="Accepted");
    const preparingOrders=liveKitchenOrders.filter(r=>String(r.order_status||"")==="Preparing");
    const readyOrders=liveKitchenOrders.filter(r=>String(r.order_status||"")==="Ready");
    const inProgress=acceptedOrders.length+preparingOrders.length+readyOrders.length;
    const unavailableItems=menu.filter(m=>Number(m.is_available||0)!==1);
    const activeRequests=kitchenRequests.filter(r=>["Pending","In Progress"].includes(String(r.status||"")));
    const orderCard=(row,actionLabel,actionAttr)=>{
      const items=restaurantOrderItems(row.cart??row.items??row.order_items);
      const place=row.table_number?`Table ${row.table_number}`:(row.room_number?`Room ${row.room_number}`:"Restaurant order");
      return `<div class="card" style="margin-bottom:10px"><div class="section-toolbar"><div><h3>Order ${esc(row.order_id||"—")}</h3><p class="section-note">${esc(place)} · ${esc(row.customer_name||"Guest")} · ${esc(row.order_date||"—")} ${esc(row.order_time||"")}</p></div><span>${esc(row.order_status||"New")}</span></div><div class="section-note" style="margin:8px 0">${items.length?items.map(i=>`<strong>${esc(i.name)}</strong> × ${esc(i.quantity)}`).join(" · "):"No item details"}</div><div class="form-actions"><button data-kitchen-detail="${esc(row.order_id||"")}">${actionLabel?"Details":"View Details"}</button>${actionLabel?`<button class="primary" ${actionAttr}="${esc(row.order_id||"")}">${esc(actionLabel)}</button>`:""}</div></div>`;
    };
    const availabilityRows=menu.map((m,i)=>`<tr><td><strong>${esc(m.item_name||"—")}</strong></td><td>${esc(m.category_name||"—")}</td><td>${money(m.price||0)}</td><td>${Number(m.is_available||0)===1?"Available":"Unavailable"}</td><td>${Number(m.is_available||0)===1?`<button data-kitchen-unavailable="${i}">Mark Unavailable</button>`:`<div class="section-note">${esc(m.availability_reason||"Not available")}</div><button data-kitchen-available="${i}">Mark Available</button>`}</td></tr>`).join("");
    const requestRows=kitchenRequests.slice(0,50).map((r,i)=>`<tr><td>${esc(r.request_id||"—")}</td><td>${esc(r.request_type||"—")}</td><td>${esc(r.title||"—")}</td><td>${esc(r.priority||"Normal")}</td><td>${esc(r.status||"Pending")}</td><td>${["Pending","In Progress"].includes(String(r.status||""))?`<button data-kitchen-request-status="${i}">Update</button>`:"—"}</td></tr>`).join("");
    const expanded=String(state.kitchenSummaryOpen||"");
    const summaryData={
      total:{title:"Total Orders",note:"All completed kitchen orders",rows:completedOrders},
      today:{title:"Today's Orders",note:"Orders completed today",rows:completedToday},
      new:{title:"New Orders",note:"Orders waiting for kitchen acceptance",rows:newOrders},
      progress:{title:"In Progress",note:"Accepted, preparing or ready orders",rows:liveKitchenOrders.filter(r=>["Accepted","Preparing","Ready"].includes(String(r.order_status||"")))},
      completed:{title:"Completed Today",note:"Orders completed today",rows:completedToday},
      unavailable:{title:"Unavailable Items",note:"Menu items currently unavailable",rows:unavailableItems},
      requests:{title:"Pending Requests",note:"Kitchen requests needing attention",rows:activeRequests},
      accepted:{title:"Accepted Orders",note:"Accepted by kitchen, not yet preparing",rows:acceptedOrders},
      preparing:{title:"Preparing Orders",note:"Currently being prepared",rows:preparingOrders},
      ready:{title:"Ready Orders",note:"Ready for waiter/service",rows:readyOrders}
    };
    const openPanel=summaryData[expanded];
    let panelHtml="";
    if(openPanel){
      if(["total","today","new","progress","completed","accepted","preparing","ready"].includes(expanded)){
        const rows=openPanel.rows;
        const actionFor=(r)=>{const status=String(r.order_status||"New");if(status==="New")return ["Accept Order","data-kitchen-accept"];if(status==="Accepted")return ["Start Preparing","data-kitchen-prepare"];if(status==="Preparing")return ["Mark Ready","data-kitchen-ready"];return ["",""];};
        panelHtml=`<div class="card kitchen-expanded-panel" style="margin-top:15px"><div class="section-toolbar"><div><h3>${esc(openPanel.title)}</h3><p class="section-note">${esc(openPanel.note)}</p></div><button data-kitchen-summary-close>Close</button></div><div class="section-note" style="margin:8px 0 12px">${rows.length} order(s)</div>${rows.length?rows.slice(0,100).map(r=>{const [label,attr]=actionFor(r);return orderCard(r,label,attr)}).join(""):"<div class=\"empty\">No orders found.</div>"}${rows.length>100?`<div class="section-note">Showing first 100 orders.</div>`:""}</div>`;
      }else if(expanded==="unavailable"){
        panelHtml=`<div class="card kitchen-expanded-panel" style="margin-top:15px"><div class="section-toolbar"><div><h3>Unavailable Items</h3><p class="section-note">Unavailable menu items cannot be ordered until Kitchen marks them available again.</p></div><button data-kitchen-summary-close>Close</button></div><div class="restaurant-data-wrap"><table class="data-table restaurant-data-table"><thead><tr><th>Item</th><th>Category</th><th>Price</th><th>Status</th><th>Action</th></tr></thead><tbody>${availabilityRows||"<tr><td colspan=\"5\">No menu items found.</td></tr>"}</tbody></table></div></div>`;
      }else if(expanded==="requests"){
        panelHtml=`<div class="card kitchen-expanded-panel" style="margin-top:15px"><div class="section-toolbar"><div><h3>Pending Kitchen Requests</h3><p class="section-note">Request gas, plates, ingredients, equipment or other kitchen support.</p></div><div class="form-actions"><button data-kitchen-summary-close>Close</button><button class="primary" data-kitchen-request-new>+ New Request</button></div></div><div class="restaurant-data-wrap"><table class="data-table restaurant-data-table"><thead><tr><th>ID</th><th>Type</th><th>Request</th><th>Priority</th><th>Status</th><th>Action</th></tr></thead><tbody>${requestRows||"<tr><td colspan=\"6\">No pending requests.</td></tr>"}</tbody></table></div></div>`;
      }
    }
    const summaryCard=(key,label,value,sub,tone,icon)=>`<div class="card metric metric-${esc(tone)} kitchen-summary-card" role="button" tabindex="0" data-kitchen-summary="${esc(key)}" aria-expanded="${expanded===key}"><div class="kitchen-card-icon" data-icon="${esc(key)}" aria-hidden="true"></div><div class="kitchen-card-body"><div class="label">${esc(label)}</div><div class="value">${esc(value)}</div><div class="sub">${esc(sub)}</div></div><span class="kitchen-card-arrow" aria-hidden="true">→</span></div>`;
    const stageCard=(key,label,value,sub,tone,icon)=>summaryCard(key,label,value,sub,tone,icon);
    const hotelName=esc(state.hotelContext?.hotel_name||"YADAV HOTEL");
    return `<section class="kitchen-dashboard-frame">
      <section class="kitchen-premium-hero">
        <div class="kitchen-hero-copy">
          <div class="kitchen-hero-eyebrow">${hotelName} • KITCHEN OPERATIONS</div>
          <h1>YADAV HOTEL<br><span>KITCHEN DASHBOARD</span></h1>
          <div class="kitchen-hero-meta"><span>● Live Kitchen</span><span>• ${completedOrders.length} completed</span><span>• ${liveKitchenOrders.length} active</span></div>
        </div>
        <div class="kitchen-hero-art" aria-hidden="true">
          <div class="kitchen-plate-ring"></div>
          <img class="kitchen-food-art kitchen-food-photo" src="/dashboard/kitchen-food-hero.png" alt="Indian restaurant meal" loading="eager">
          <div class="kitchen-hero-badge"><span>✦</span><div><strong>Fresh • Ready • Served</strong><small>Kitchen workflow</small></div></div>
        </div>
      </section>
      <div class="kitchen-dashboard-body">
        <section class="kitchen-overview-block">
          <div class="kitchen-section-title"><div><span>LIVE OVERVIEW</span><h2>Kitchen at a glance</h2></div><p>Tap any card to open its live details.</p></div>
          <div class="grid cards kitchen-summary-grid">${summaryCard("total","Total Orders",completedOrders.length,"All completed kitchen orders","blue","⌁")}${summaryCard("today","Today's Orders",completedToday.length,"Orders completed today","purple","▣")}${summaryCard("new","New Orders",newOrders.length,"Waiting for kitchen action","orange","•")}${summaryCard("progress","In Progress",inProgress,"Accepted, preparing or ready","gold","⌁")}${summaryCard("completed","Completed Today",completedToday.length,"Completed restaurant orders today","green","✓")}${summaryCard("unavailable","Unavailable Items",unavailableItems.length,"Menu items currently unavailable","rose","!")}${summaryCard("requests","Pending Requests",activeRequests.length,"Kitchen requests needing attention","orange","!")}</div>
          ${(!['accepted','preparing','ready','unavailable','requests'].includes(expanded)?panelHtml:"")}
        </section>
        <section class="kitchen-operations-card"><div class="kitchen-section-title compact"><div><span>KITCHEN FLOW</span><h2>Operational View</h2></div><p>Accepted → Preparing → Ready</p></div><div class="grid three kitchen-stage-grid">${stageCard("accepted","Accepted",acceptedOrders.length,"Accepted, not yet preparing","blue","✓")}${stageCard("preparing","Preparing",preparingOrders.length,"Currently being prepared","orange","⌁")}${stageCard("ready","Ready",readyOrders.length,"Ready for waiter/service","green","✓")}</div>${["accepted","preparing","ready"].includes(expanded)?panelHtml:""}</section>
        ${["unavailable","requests"].includes(expanded)?panelHtml:""}
      </div>
    </section>`;
  }
  const tabs=`<div class="room-tabs restaurant-tabs" role="tablist" aria-label="Restaurant sections">
    ${restaurantTab("overview","Overview")}
    ${restaurantTab("menu","Menu Management",menu.length)}
    ${restaurantTab("tables","Tables",activeTables.length)}
    ${restaurantTab("orders","Orders",orders.length)}
    ${restaurantTab("kitchen","Kitchen",kitchen.length)}
    ${restaurantTab("bookings","Table Bookings",bookings.length)}
  </div>`;

  let sectionHtml="";
  if(restaurantSection==="menu"){
    sectionHtml=`<div class="card room-section-card restaurant-section-card"><div class="section-toolbar"><div><h3>Menu Management View</h3><p class="section-note">Manage restaurant categories and menu items.</p></div><div class="actions">${isActionAllowed("restaurant_menu_create")?'<button data-menu-add-category>Add Category</button> <button class="primary" data-menu-add>+ Add Item</button>':""}</div></div>${restaurantCompactTable(menu,menuColumns,menuActions)}</div>`;
  }else if(restaurantSection==="tables"){
    sectionHtml=`<div class="card room-section-card restaurant-section-card"><div class="section-toolbar"><div><h3>Table Status</h3><p class="section-note">Manage occupied and available restaurant tables.</p></div></div>${restaurantTableStatusCompact(tables)}</div>`;
  }else if(restaurantSection==="orders"){
    const todayOrderDate=dateNow();
    const tomorrowOrderDate=addRestaurantOrderDays(todayOrderDate,1);
    const filteredRestaurantOrders=allRestaurantOrders.filter(row=>{
      const orderDate=parseRestaurantOrderDate(row.order_date||row.created_at||row.order_datetime);
      if(restaurantOrderDateFilter==="all")return true;
      if(!orderDate)return false;
      if(restaurantOrderDateFilter==="today")return orderDate===todayOrderDate;
      if(restaurantOrderDateFilter==="tomorrow")return orderDate===tomorrowOrderDate;
      if(restaurantOrderDateFilter==="upcoming")return orderDate>=todayOrderDate;
      if(restaurantOrderDateFilter==="past")return orderDate<todayOrderDate;
      if(restaurantOrderDateFilter==="custom")return restaurantOrderCustomDate ? orderDate===restaurantOrderCustomDate : true;
      return true;
    });
    const initialOrderRows=filteredRestaurantOrders;
    window.__restaurantOrderRows=initialOrderRows;
    sectionHtml=`<div class="card room-section-card restaurant-section-card"><div class="section-toolbar"><div><h3>Restaurant Orders</h3><p class="section-note">Search orders, check dates and manage the current order lifecycle.</p></div><button class="primary" data-action="order">+ Restaurant Order</button></div>
      <div class="toolbar room-filter-bar restaurant-order-toolbar">
        <input class="search" id="restaurant-order-search" placeholder="Search order, guest, mobile or table…">
        <select id="restaurant-order-date">
          <option value="all" ${restaurantOrderDateFilter==="all"?"selected":""}>All dates</option>
          <option value="today" ${restaurantOrderDateFilter==="today"?"selected":""}>Today</option>
          <option value="tomorrow" ${restaurantOrderDateFilter==="tomorrow"?"selected":""}>Tomorrow</option>
          <option value="upcoming" ${restaurantOrderDateFilter==="upcoming"?"selected":""}>Upcoming</option>
          <option value="past" ${restaurantOrderDateFilter==="past"?"selected":""}>Past</option>
          <option value="custom" ${restaurantOrderDateFilter==="custom"?"selected":""}>Custom date</option>
        </select>
        <input id="restaurant-order-custom-date" type="date" value="${esc(restaurantOrderCustomDate)}" aria-label="Order date" title="Choose an order date">
        <select id="restaurant-order-status">${statusOptions.map(x=>`<option value="${esc(x)}">${x||"All statuses"}</option>`).join("")}</select>
        <button id="restaurant-order-search-btn">Search</button><button id="restaurant-order-today">Today</button><button id="restaurant-order-clear">Clear</button>
      </div>
      <div class="section-note" style="margin:8px 0 12px">Showing ${initialOrderRows.length} order(s)</div>
      <div id="restaurant-order-results">${restaurantCompactTable(initialOrderRows,[{key:"order_id",label:"Order ID"},{key:"order_date",label:"Date"},{key:"customer_name",label:"Guest"},{key:"customer_mobile",label:"Mobile"},{key:"table_number",label:"Table"},{key:"grand_total",label:"Total"},{key:"paid_amount",label:"Paid"},{key:"order_status",label:"Status"}],orderActions)}</div></div>`;
  }else if(restaurantSection==="kitchen"){
    const kitchenStatusFilter=String(state.restaurantKitchenStatus||"all");
    const filteredKitchen=kitchen.filter(row=>kitchenStatusFilter==="all" || String(row.order_status||"New")===kitchenStatusFilter);
    const kitchenCounts={New:0,Accepted:0,Preparing:0,Ready:0,Served:0};
    kitchen.forEach(row=>{const status=String(row.order_status||"New");if(Object.prototype.hasOwnProperty.call(kitchenCounts,status))kitchenCounts[status]+=1;});
    const kitchenActionLabel=(status)=>({New:"Accept Order",Accepted:"Start Preparing",Preparing:"Mark Ready",Ready:"View Details",Served:"View Details"}[status]||"View Details");
    window.__restaurantKitchenRows=filteredKitchen;
    const kitchenRowsHtml=filteredKitchen.length
      ? `<div class="restaurant-data-wrap"><table class="data-table restaurant-data-table"><thead><tr>${kitchenColumns.map(c=>`<th>${esc(c.label)}</th>`).join("")}<th>Items</th><th>Total</th><th>Actions</th></tr></thead><tbody>${filteredKitchen.map((r,i)=>{const status=String(r.order_status||"New");const items=restaurantOrderItems(r.cart??r.items??r.order_items);const itemSummary=items.length?items.map(item=>`${esc(item.name)} × <strong>${esc(item.quantity)}</strong>`).join("<br>"):"—";const action=isActionAllowed("order_status")&&status!=="Served"?`<button data-kitchen-detail="${i}">Details</button> <button data-kitchen-next="${i}">${kitchenActionLabel(status)}</button>`:`<button data-kitchen-detail="${i}">Details</button>`;return `<tr>${kitchenColumns.map(c=>`<td>${cell(r[c.key])}</td>`).join("")}<td>${itemSummary}</td><td>${money(r.grand_total||0)}</td><td>${action}</td></tr>`;}).join("")}</tbody></table></div>`
      : `<div class="empty">No kitchen orders found for this status.</div>`;
    sectionHtml=`<div class="card room-section-card restaurant-section-card">
      <div class="section-toolbar"><div><h3>Kitchen Operational View</h3><p class="section-note">Manage the live kitchen queue from order received to served.</p></div></div>
      <div class="grid cards" style="margin:12px 0 15px">
        ${metric("New",kitchenCounts.New,"Waiting for kitchen","blue","•")}
        ${metric("Preparing",kitchenCounts.Preparing,"Currently being prepared","orange","⌁")}
        ${metric("Ready",kitchenCounts.Ready,"Ready to serve","green","✓")}
        ${metric("Served",kitchenCounts.Served,"Served to guest","purple","▣")}
      </div>
      <div class="toolbar room-filter-bar restaurant-order-toolbar">
        <select id="restaurant-kitchen-status">
          <option value="all" ${kitchenStatusFilter==="all"?"selected":""}>All kitchen orders</option>
          <option value="New" ${kitchenStatusFilter==="New"?"selected":""}>New</option>
          <option value="Preparing" ${kitchenStatusFilter==="Preparing"?"selected":""}>Preparing</option>
          <option value="Ready" ${kitchenStatusFilter==="Ready"?"selected":""}>Ready</option>
          <option value="Served" ${kitchenStatusFilter==="Served"?"selected":""}>Served</option>
        </select>
        <button id="restaurant-kitchen-clear">Clear</button>
      </div>
      <div class="section-note" style="margin:8px 0 12px">Showing ${filteredKitchen.length} kitchen order(s)</div>
      ${kitchenRowsHtml}
    </div>`;
  }else if(restaurantSection==="bookings"){
    sectionHtml=`<div class="card room-section-card restaurant-section-card"><div class="section-toolbar"><div><h3>Table Bookings</h3><p class="section-note">Restaurant table reservation records.</p></div></div>${restaurantCompactTable(bookings,bookingColumns)}</div>`;
  }else{
    sectionHtml=`<div class="grid two room-overview-grid restaurant-overview-grid">
      <div class="card room-overview-card"><div class="section-toolbar"><div><h3>Menu Management</h3><p class="section-note">Manage categories and menu items.</p></div><button data-restaurant-section="menu">Open</button></div><div class="room-preview"><strong>${menu.length}</strong><span>menu items</span></div></div>
      <div class="card room-overview-card"><div class="section-toolbar"><div><h3>Restaurant Orders</h3><p class="section-note">Current and completed restaurant orders.</p></div><button data-restaurant-section="orders">Open</button></div><div class="room-preview"><strong>${o.orders_today||0}</strong><span>orders today</span></div></div>
      <div class="card room-overview-card"><div class="section-toolbar"><div><h3>Table Status</h3><p class="section-note">Current restaurant table occupancy.</p></div><button data-restaurant-section="tables">Open</button></div><div class="room-preview"><strong>${o.available_tables||0}</strong><span>available tables</span></div><div class="room-status-summary"><span><b>${o.occupied_tables||0}</b> Occupied</span><span><b>${o.available_tables||0}</b> Available</span></div></div>
      <div class="card room-overview-card"><div class="section-toolbar"><div><h3>Kitchen Operations</h3><p class="section-note">Current kitchen queue.</p></div><button data-restaurant-section="kitchen">Open</button></div><div class="room-preview"><strong>${kitchen.length}</strong><span>kitchen orders</span></div></div>
      <div class="card room-overview-card"><div class="section-toolbar"><div><h3>Table Bookings</h3><p class="section-note">Restaurant table reservation records.</p></div><button data-restaurant-section="bookings">Open</button></div><div class="room-preview"><strong>${bookings.length}</strong><span>booking records</span></div></div>
      <div class="card room-overview-card"><div class="section-toolbar"><div><h3>Table Cleaning</h3><p class="section-note">Current restaurant table cleaning workload.</p></div><button data-restaurant-section="tables">Open</button></div><div class="room-status-summary"><span><b>${cleaningRequiredTables}</b> Cleaning Required</span><span><b>${cleaningInProgressTables}</b> Cleaning</span><span><b>${o.available_tables||0}</b> Available</span></div></div>
    </div>`;
  }

  return `<div class="restaurant-workspace">`+
    pageHead("Restaurant / POS Dashboard","Restaurant overview, orders, tables, payments and kitchen operations",`<button class="primary" data-action="order">+ Restaurant Order</button>`)+
    `<div class="restaurant-revenue-strip"><div class="restaurant-revenue-title"><h2>Restaurant Revenue</h2><span>Sales, daily performance and outstanding balances</span></div><div class="restaurant-revenue-grid">${metric("Total Sales Revenue",money(totalSalesRevenue),"All-time non-cancelled restaurant sales","green","₹")}${metric("Revenue Today",money(o.revenue_today||0),"Today's restaurant sales","gold","₹")}${metric("Orders Today",o.orders_today||0,"Non-cancelled orders","blue","⌁")}${metric("Pending Payments",money(o.pending_payments||0),"Outstanding today","rose","₹")}</div></div>`+
    `<div class="grid cards restaurant-kpis">${metric("Available Tables",o.available_tables||0,"Current table status","green","✓")}${metric("Occupied Tables",o.occupied_tables||0,"Current table status","orange","•")}${metric("Kitchen Orders",kitchen.length,"Current kitchen queue","blue","⌁")}${metric("Table Bookings",bookings.length,"Restaurant table bookings","purple","▣")}</div>`+
    tabs+sectionHtml+`</div>`;
}

async function billing(){
  const [summary,inv,payments]=await Promise.all([
    api("/billing/summary"),
    api(`/billing/invoices${state.search?`?search=${encodeURIComponent(state.search)}`:""}`),
    api("/room-payments?limit=200")
  ]);
  const d=summary.data||{}, rows=inv.data||[], paymentRows=payments.data||[];
  const actions=`<button data-invoice-detail="{{i}}">Details</button>`;
  return pageHead("Billing & Payments","Invoices, balances, room settlements and payment history",`<button data-refresh>Refresh</button>`)
    +`<div class="grid cards">${metric("Invoices",d.invoice_count||0,"Issued invoices")}${metric("Room Paid",money(d.room?.paid||0),"Room payments")}${metric("Room Balance",money(d.room?.balance||0),"Outstanding")}${metric("Restaurant Paid",money(d.restaurant?.paid||0),"Restaurant payments")}${metric("Restaurant Balance",money(d.restaurant?.balance||0),"Outstanding")}</div>`
    +`<div class="card" style="margin-top:15px"><h3>Payment History</h3><p class="section-note">All recorded room payment transactions, including reservation advances and later settlements.</p>${table(paymentRows)}</div>`
    +`<div class="card" style="margin-top:15px"><div class="toolbar"><input class="search" id="billing-search" placeholder="Invoice number, source ID or source type…" value="${esc(state.search||"")}"><button id="billing-search-btn">Search</button><button id="billing-clear">Clear</button></div>${table(rows,actions)}</div>`;
}
async function inventory(){
 const [items,low,val,cats,units,hist,batches]=await Promise.all([api("/inventory/items"),api("/inventory/low-stock"),api("/inventory/valuation"),api("/inventory/categories"),api("/inventory/units"),api("/inventory/history?limit=100"),api("/inventory/batches?limit=100")]);
 const itemRows=items.data||[], lowRows=low.data||[], historyRows=hist.data||[], batchRows=batches.data||[];
 window.__inventoryItems=itemRows;
 const actions=isActionAllowed("inventory_stock")?'<button data-inv-stock="{{i}}">Stock In/Out</button>':'';
 return pageHead("Inventory","Stock, alerts, valuation, batches and movement history")+`<div class="grid cards">${metric("Items",itemRows.length,"Inventory records")}${metric("Low Stock",lowRows.length,"Needs attention")}${metric("Valuation",money(val.data?.inventory_value),"Current valuation")}${metric("Categories",cats.data?.length||0,"Configured categories")}</div><div class="grid two" style="margin-top:15px"><div class="card"><h3>Inventory Items</h3><div class="toolbar"><input class="search" id="inventory-search" placeholder="Item ID or item name…" value="${esc(state.inventorySearch||"")}"><button id="inventory-search-btn">Search</button><button id="inventory-clear">Clear</button></div>${table(itemRows,actions)}</div><div class="card ${lowRows.length?"alert":"success"}"><h3>Low Stock / Reorder</h3>${table(lowRows)}</div></div><div class="grid two" style="margin-top:15px"><div class="card"><h3>Batch / Lot & Expiry</h3>${table(batchRows)}</div><div class="card"><h3>Stock History</h3>${table(historyRows)}</div></div><div class="card" style="margin-top:15px"><h3>Master Data</h3><div class="grid two"><div>${table(cats.data||[])}</div><div>${table(units.data||[])}</div></div></div>`;
}
async function procurement(){
 const [s,p,r,o,t]=await Promise.all([
  api("/suppliers"),
  api("/procurement/purchase-orders"),
  api("/procurement/receivings"),
  api("/procurement/outstanding"),
  api("/procurement/payment-terms")
 ]);
 const suppliers=s.data||[], orders=p.data||[], receiving=r.data||[], outstanding=o.data||[], terms=t.data||[];
 return pageHead("Suppliers & Procurement","Supplier master, purchase orders, receiving, terms and outstanding")+`
 <div class="grid three">
  <div class="card"><h3>Supplier Overview</h3><div class="metric">${suppliers.length}</div><p>Suppliers</p><div class="toolbar"><input id="supplier-search" placeholder="Search supplier / GST / mobile"><button id="supplier-search-btn">Search</button></div><div id="supplier-results">${table(suppliers)}</div></div>
  <div class="card"><h3>Purchase Orders</h3><div class="metric">${orders.length}</div><p>Purchase Orders</p>${table(orders)}</div>
  <div class="card"><h3>Purchase Receiving</h3><div class="metric">${receiving.length}</div><p>Receiving records</p>${table(receiving)}</div>
 </div>
 <div class="grid two">
  <div class="card"><h3>Supplier Outstanding</h3>${table(outstanding)}</div>
  <div class="card"><h3>Payment Terms</h3>${table(terms)}</div>
 </div>`;
}
async function hr(){
 const [s,d,g,a,l,sa,p,sum]=await Promise.all([api("/staff"),api("/departments"),api("/designations"),api("/attendance"),api("/leave"),api("/salary"),api("/payroll"),api("/hr/summary")]);
 const staffRows=s.data||[], departments=d.data||[], designationRows=g.data||[], attendance=a.data||[], leave=l.data||[], salary=sa.data||[], payroll=p.data||[], summary=sum.data||{};
 const statusCounts=staffRows.reduce((acc,row)=>{const k=row.status||"Unknown";acc[k]=(acc[k]||0)+1;return acc},{});
 let userSection="";
 if(hasPermission("Users","View")){
   const [u,r]=await Promise.all([api("/admin/users"),api("/admin/roles")]);
   const users=u.data||[], roles=r.data||[];
   const roleOptions=roles.filter(x=>x.status==="Active").map(x=>x.role_name);
   const createButton=hasPermission("Users","Create")?`<button class="primary" data-user-create>+ Create Login User</button>`:"";
   window.__hrUserRoles=roleOptions;
   userSection=`<div class="card" style="margin-top:15px"><div class="page-head"><div><h3>Login Users & Roles</h3><span class="section-note">${users.length} login user(s)</span></div>${createButton}</div>${table(users)}</div>`;
 }
 return pageHead("Staff & HR","Staff profiles, departments, designations, attendance, leave, salary and payroll")+
 `<div class="grid cards">${metric("Total Staff",summary.total_staff||0,"All staff")}${metric("Active Staff",summary.active_staff||0,"New / Active / On Leave")}${metric("Departments",summary.departments||0,"Active departments")}${metric("Designations",summary.designations||0,"Active designations")}${metric("Pending Leave",summary.pending_leave||0,"Requests")}${metric("Monthly Staff Cost",money(summary.monthly_staff_cost||0),"Current staff salary")}</div>`+
 `<div class="grid three" style="margin-top:15px"><div class="card"><h3>Staff List & Profiles</h3>${table(staffRows)}</div><div class="card"><h3>Departments</h3>${table(departments)}</div><div class="card"><h3>Designations</h3>${table(designationRows)}</div></div>`+
 `<div class="grid three" style="margin-top:15px"><div class="card"><h3>Attendance</h3>${table(attendance)}</div><div class="card"><h3>Leave</h3>${table(leave)}</div><div class="card"><h3>Staff Status</h3>${table(Object.entries(statusCounts).map(([status,count])=>({status,staff_count:count})))}<p class="section-note">Active staff: ${summary.active_staff||0} · Separated: ${summary.separated_staff||0}</p></div></div>`+
 `<div class="grid two" style="margin-top:15px"><div class="card"><h3>Salary</h3>${table(salary)}</div><div class="card"><h3>Payroll</h3>${table(payroll)}</div></div>`+
 userSection+
 `<div class="card" style="margin-top:15px"><h3>HR Operational Summary</h3>${table([summary])}</div>`;
}
async function expenses(){
 const q=new URLSearchParams();
 const start=document.getElementById("expense-start")?.value, end=document.getElementById("expense-end")?.value, search=document.getElementById("expense-search")?.value, cat=document.getElementById("expense-category")?.value, pay=document.getElementById("expense-payment")?.value, approval=document.getElementById("expense-approval")?.value, recurring=document.getElementById("expense-recurring")?.value;
 if(start)q.set("start_date",start);if(end)q.set("end_date",end);if(search)q.set("search",search);if(cat)q.set("category_id",cat);if(pay)q.set("payment_method",pay);if(approval)q.set("approval_status",approval);if(recurring)q.set("recurring",recurring);
 const suffix=q.toString()?`?${q}`:"";
 const [e,s,c,v,d]=await Promise.all([api(`/expenses${suffix}`),api(`/expenses/summary${suffix}`),api("/expenses/categories"),api("/expenses/vendors"),api("/expenses/departments")]);
 const rows=e.data||[], summary=s.data||{};
 const options=(items,valueKey,labelKey)=>items.map(x=>`<option value="${esc(x[valueKey])}">${esc(x[labelKey])}</option>`).join("");
 return pageHead("Expense Management","Expense records, categories, vendors, approvals and recurring expenses",`<button class="primary" data-action="expense">+ New Expense</button>`)+
 `<div class="card filter-card"><div class="form-grid"><label>From<input id="expense-start" type="date" value="${esc(start||"")}"></label><label>To<input id="expense-end" type="date" value="${esc(end||"")}"></label><label>Search<input id="expense-search" placeholder="ID, name, vendor, receipt" value="${esc(search||"")}"></label><label>Category<select id="expense-category"><option value="">All</option>${options(c.data||[],"category_id","category_name")}</select></label><label>Payment Method<select id="expense-payment"><option value="">All</option>${["Cash","Card","UPI","Online","Bank Transfer","Cheque","Other"].map(x=>`<option ${x===pay?"selected":""}>${x}</option>`).join("")}</select></label><label>Approval<select id="expense-approval"><option value="">All</option>${["Pending","Approved","Rejected"].map(x=>`<option ${x===approval?"selected":""}>${x}</option>`).join("")}</select></label><label>Recurring<select id="expense-recurring"><option value="">All</option><option value="true" ${recurring==="true"?"selected":""}>Recurring</option><option value="false" ${recurring==="false"?"selected":""}>Non-recurring</option></select></label><div class="form-actions"><button class="primary" data-expense-filter>Apply Filters</button><button data-expense-clear>Clear</button></div></div></div>`+
 `<div class="grid cards">${metric("Total Expense",money(summary.total),`${summary.count||0} record(s)`)}${metric("Pending Approval",money((summary.by_approval||[]).find(x=>x.approval_status==="Pending")?.amount||0),"Awaiting approval")}${metric("Recurring Records",(summary.recurring||[]).length,"Active recurring records")}${metric("Vendors",(v.data||[]).length,"Available vendors")}</div>`+
 `<div class="grid three" style="margin-top:15px"><div class="card"><h3>Expense Records</h3>${table(rows)}</div><div class="card"><h3>Categories</h3>${table(c.data||[])}</div><div class="card"><h3>Vendors</h3>${table(v.data||[])}</div></div>`+
 `<div class="grid three" style="margin-top:15px"><div class="card"><h3>Payment Method Report</h3>${table(summary.by_payment_method||[])}</div><div class="card"><h3>Category Report</h3>${table(summary.by_category||[])}</div><div class="card"><h3>Approval Report</h3>${table(summary.by_approval||[])}</div></div>`+
 `<div class="grid two" style="margin-top:15px"><div class="card"><h3>Departments</h3>${table(d.data||[])}</div><div class="card"><h3>Recurring Expenses / Next Due</h3>${table(summary.recurring||[])}</div></div>`;
}
async function feedback(){
 const search=state.feedbackSearch||"", category=state.feedbackCategory||"", status=state.feedbackStatus||"", rating=state.feedbackRating||"", complaint=state.feedbackComplaints||"", follow=state.feedbackFollow||"";
 const q=new URLSearchParams(); if(search)q.set("search",search);if(category)q.set("category",category);if(status)q.set("status",status);if(rating)q.set("rating",rating);if(complaint)q.set("complaint_only","true");if(follow)q.set("follow_up_required","true");
 const [f,s]=await Promise.all([api(`/feedback${q.toString()?`?${q}`:""}`),api("/feedback/satisfaction")]);
 const rows=f.data||[];window.__feedbackRows=rows;const complaints=rows.filter(x=>x.complaint);window.__complaintRows=complaints;const pending=complaints.filter(x=>!["Resolved","Closed"].includes(x.status));
 const actions=isActionAllowed("feedback_update")?`<button data-feedback-manage="{{i}}">Manage</button>`:"";
 return pageHead("Feedback & Guest Experience","Ratings, reviews, complaints, follow-ups and guest satisfaction")+
 `<div class="card filter-card"><div class="form-grid"><label>Search<input id="feedback-search" value="${esc(search)}" placeholder="Guest, feedback, complaint, issue"></label><label>Category<select id="feedback-category"><option value="">All</option>${["General","Room","Restaurant","Cleanliness","Staff","Service","Facilities","Billing","Other"].map(x=>`<option ${x===category?"selected":""}>${x}</option>`).join("")}</select></label><label>Rating<select id="feedback-rating"><option value="">All</option>${[1,2,3,4,5].map(x=>`<option ${String(x)===String(rating)?"selected":""}>${x}</option>`).join("")}</select></label><label>Status<select id="feedback-status"><option value="">All</option>${["Open","In Progress","Resolved","Closed"].map(x=>`<option ${x===status?"selected":""}>${x}</option>`).join("")}</select></label><label>Complaints<select id="feedback-complaints"><option value="">All feedback</option><option value="1" ${complaint?"selected":""}>Complaints only</option></select></label><label>Follow-up<select id="feedback-follow"><option value="">All</option><option value="1" ${follow?"selected":""}>Follow-up required</option></select></label><div class="form-actions"><button class="primary" data-feedback-filter>Apply Filters</button><button data-feedback-clear>Clear</button></div></div></div>`+
 `<div class="grid cards">${metric("Feedback",rows.length,"Current filtered records")}${metric("Complaints",complaints.length,"Complaint records")}${metric("Open Issues",pending.length,"Needs resolution")}${metric("Follow-ups",rows.filter(x=>Number(x.follow_up_required||0)===1).length,"Required follow-ups")}</div>`+
 `<div class="grid two" style="margin-top:15px"><div class="card"><h3>Guest Satisfaction Data</h3>${table([s.data||{}])}</div><div class="card"><h3>Complaint Management</h3>${table(complaints,isActionAllowed("feedback_update")?`<button data-complaint-manage="{{i}}">Manage</button>`:"")}</div></div>`+
 `<div class="card" style="margin-top:15px"><h3>Feedback / Reviews</h3>${table(rows,actions)}</div>`;
}
async function notifications(){
 const search=document.getElementById("notification-search")?.value.trim()||"";
 const eventType=document.getElementById("notification-event")?.value||"";
 const channel=document.getElementById("notification-channel")?.value||"";
 const status=document.getElementById("notification-status")?.value||"";
 const unread=document.getElementById("notification-unread")?.checked||false;
 const q=new URLSearchParams();if(eventType)q.set("event_type",eventType);if(channel)q.set("channel",channel);if(status)q.set("status",status);if(unread)q.set("unread_only","true");q.set("limit","200");
 const [n,c]=await Promise.all([api(`/notifications?${q}`),api("/notifications/channels")]);
 const term=search.toLowerCase();
 const rows=(n.data||[]).filter(x=>!term||[x.event_id,x.event_type,x.reference_id,x.recipient_name,x.title,x.message].some(v=>String(v||"").toLowerCase().includes(term)));
 window.__notificationRows=rows;
 return pageHead("Notifications & Communication","Event inbox, history, search, status and communication channels")+
 `<div class="card filter-card"><div class="form-grid"><label>Search<input id="notification-search" value="${esc(search)}" placeholder="Event, guest, title, message"></label><label>Event Type<select id="notification-event"><option value="">All events</option>${["Booking","Payment","Cancellation","Check-in","Check-out","Low Stock","Feedback","Transportation"].map(x=>`<option ${x===eventType?"selected":""}>${x}</option>`).join("")}</select></label><label>Channel<select id="notification-channel"><option value="">All channels</option>${(c.data||[]).map(x=>`<option value="${esc(x.channel_code)}" ${x.channel_code===channel?"selected":""}>${esc(x.channel_name)}</option>`).join("")}</select></label><label>Status<select id="notification-status"><option value="">All statuses</option>${["Queued","Pending Integration","Sent","Failed","Read"].map(x=>`<option ${x===status?"selected":""}>${x}</option>`).join("")}</select></label><label class="checkbox-field"><input id="notification-unread" type="checkbox" ${unread?"checked":""}> Unread only</label><div class="form-actions"><button class="primary" data-notification-filter>Apply Filters</button><button data-notification-clear>Clear</button></div></div></div>`+
 `<div class="grid two"><div class="card"><h3>Notification Inbox / History</h3>${table(rows,isActionAllowed("notification_read")?`<button data-read="{{i}}">Mark read</button>`:"")}</div><div class="card"><h3>Communication Channels</h3>${table(c.data||[])}</div></div>`;
}
async function transport(){
 const qs=new URLSearchParams();
 if(state.transportSearch)qs.set("search",state.transportSearch);
 if(state.transportStatus)qs.set("status",state.transportStatus);
 if(state.transportIntegration)qs.set("integration_status",state.transportIntegration);
 const [r,v,d]=await Promise.all([api(`/transportation/requests${qs.toString()?`?${qs}`:""}`),api("/transportation/vehicles"),api("/transportation/drivers")]);
 window.__transportRows=r.data||[]; window.__vehicleRows=v.data||[]; window.__driverRows=d.data||[];
 const reqActions=`<button data-transport-detail="{{i}}">Details</button>${isActionAllowed("transport_update")?` <button data-transport-edit="{{i}}">Manage</button>`:""}`;
 const vehicleActions=isActionAllowed("transport_update")?`<button data-vehicle-status="{{i}}">Status</button>`:"";
 const driverActions=isActionAllowed("transport_update")?`<button data-driver-status="{{i}}">Status</button>`:"";
 return pageHead("Transportation","Requests, vehicles, drivers, providers, integration and trip history",isActionAllowed("transport")?`<button class="primary" data-action="transport">+ Request</button>`:"")
 +`<div class="card filter-card"><div class="form-grid"><label>Search<input id="transport-search" value="${esc(state.transportSearch||"")}" placeholder="Request, guest, pickup, drop, vehicle, driver"></label><label>Status<select id="transport-status"><option value="">All statuses</option>${["Requested","Confirmed","Assigned","Driver On The Way","In Transit","Completed","Cancelled","No-Show"].map(x=>`<option ${x===(state.transportStatus||"")?"selected":""}>${x}</option>`).join("")}</select></label><label>Integration<select id="transport-integration"><option value="">All</option>${["Not Integrated","Pending Integration","Integrated","Failed"].map(x=>`<option ${x===(state.transportIntegration||"")?"selected":""}>${x}</option>`).join("")}</select></label><div class="form-actions"><button class="primary" data-transport-filter>Apply</button><button data-transport-clear>Clear</button></div></div></div>`
 +`<div class="grid three"><div class="card"><h3>Requests / History</h3>${table(r.data||[],reqActions)}</div><div class="card"><h3>Vehicles</h3>${table(v.data||[],vehicleActions)}</div><div class="card"><h3>Drivers</h3>${table(d.data||[],driverActions)}</div></div>`;
}
const REPORTS=[["revenue","Revenue"],["room-revenue","Room Revenue"],["restaurant-revenue","Restaurant Revenue"],["occupancy","Occupancy"],["adr","ADR"],["revpar","RevPAR"],["booking-trends","Booking Trends"],["cancellation","Cancellation"],["no-show","No-show"],["customer-trends","Customer Trends"],["inventory-trends","Inventory Trends"],["expense-trends","Expense Trends"],["department-performance","Department Performance"],["staff","Staff Reports"],["profitability","Profitability"]];
async function reports(){
 const start=document.getElementById("report-start")?.value||""; const end=document.getElementById("report-end")?.value||"";
 const q=new URLSearchParams(); if(start)q.set("start_date",start); if(end)q.set("end_date",end); const suffix=q.toString()?`?${q}`:"";
 const [op,...results]=await Promise.all([api(`/reports/operational${suffix}`),...REPORTS.map(async ([key,label])=>{try{const r=await api(`/reports/${key}${suffix}`);return [label,r.data]}catch(e){return [label,{error:e.message}]} })]);
 const o=op.data||{}; const rev=o.revenue||{}; const occ=o.occupancy||{}; const prof=o.profitability||{};
 return pageHead("Reports & Analytics","Management analytics, trends and operational performance")+
 `<div class="card filter-card"><div class="form-grid"><label>From Date<input id="report-start" type="text" value="${esc(start)}" placeholder="DD-MM-YYYY"></label><label>To Date<input id="report-end" type="text" value="${esc(end)}" placeholder="DD-MM-YYYY"></label><div class="form-actions"><button class="primary" data-report-filter>Apply</button><button data-report-clear>Clear</button></div></div></div>`+
 `<div class="grid cards"><div class="card"><h3>Dashboard Analytics</h3><span class="section-note">Operational and management KPI summary</span></div>${metric("Total Revenue",money(rev.total_revenue),`Room ${money(rev.room_revenue)} • Restaurant ${money(rev.restaurant_revenue)}`)}${metric("Occupancy",Number(occ.occupancy_rate||0).toFixed(1)+"%",`${occ.sold_room_nights||0} sold / ${occ.available_room_nights||0} available room nights`)}${metric("ADR",money(results.find(x=>x[0]==="ADR")?.[1]?.adr),"Room revenue / sold room nights")}${metric("RevPAR",money(results.find(x=>x[0]==="RevPAR")?.[1]?.revpar),"Room revenue / available room nights")}${metric("Profitability",money(prof.profit),`${Number(prof.margin||0).toFixed(1)}% margin foundation`)}${metric("Cancellations",o.cancellations?.count||0,"Room + restaurant")}${metric("No-shows",o.no_shows?.count||0,"Room bookings")}</div>`+
 `<div class="card" style="margin-top:15px"><h3>Operational Reports</h3>${table([o])}</div>`+`<div class="grid three" style="margin-top:15px">${results.map(([l,d])=>`<div class="card"><h3>${esc(l)}</h3>${d?.error?`<p class="form-error">${esc(d.error)}</p>`:table([d||{}])}</div>`).join("")}</div>`;
}
async function audit(){
 const q=new URLSearchParams();
 const fields=[["search","audit-search"],["actor_username","audit-user"],["module","audit-module"],["action","audit-action"],["status","audit-status"],["date_from","audit-start"],["date_to","audit-end"],["request_id","audit-request"]];
 fields.forEach(([key,id])=>{const v=document.getElementById(id)?.value?.trim();if(v)q.set(key,v)});
 const suffix=q.toString()?`?${q}`:"";
 const [a,u,r,p]=await Promise.all([api(`/admin/audit${suffix}`),api("/admin/users"),api("/admin/roles"),api("/admin/permissions")]);
 const rows=a.data||[];
 const actions=rows.map((row,i)=>`<button data-audit-detail="${i}">Detail</button>`).join(" ");
 window.__auditRows=rows;
 return pageHead("Audit & Activity","Audit history, user activity, actions, record references and request traceability",`<button class="primary" data-backup>Backup Database</button>`)+
 `<div class="card filter-card"><div class="form-grid"><label>Search<input id="audit-search" value="${esc(state.auditSearch||"")}" placeholder="User, module, action, record, details, request ID"></label><label>User<input id="audit-user" placeholder="Username"></label><label>Module<input id="audit-module" placeholder="Module"></label><label>Action<input id="audit-action" placeholder="CREATE / UPDATE..."></label><label>Status<select id="audit-status"><option value="">All status</option>${["SUCCESS","FAILED","INFO"].map(x=>`<option>${x}</option>`).join("")}</select></label><label>From Date<input id="audit-start" placeholder="YYYY-MM-DD"></label><label>To Date<input id="audit-end" placeholder="YYYY-MM-DD"></label><label>Request / Correlation ID<input id="audit-request" placeholder="Request ID"></label><div class="form-actions"><button class="primary" data-audit-filter>Apply</button><button data-audit-clear>Clear</button></div></div></div>`+
 `<div class="grid cards">${metric("Audit Records",rows.length,"Current filtered result")}${metric("Users",(u.data||[]).length,"Hotel users")}${metric("Roles",(r.data||[]).length,"Configured roles")}${metric("Permissions",(p.data||[]).length,"Active permissions")}</div>`+
 `<div class="card" style="margin-top:15px"><h3>Audit History / Activity History</h3>${table(rows,actions)}</div>`+
 `<div class="grid three" style="margin-top:15px"><div class="card"><h3>User Activity</h3>${table(rows.map(x=>({username:x.actor_username,role:x.actor_role,module:x.module,action:x.action,timestamp:istDateTime(x.created_at)})))}</div><div class="card"><h3>Record References</h3>${table(rows.map(x=>({record_type:x.record_type,record_id:x.record_id,module:x.module,action:x.action})))}</div><div class="card"><h3>Request / Correlation Trace</h3>${table(rows.map(x=>({request_id:x.request_id,username:x.actor_username,action:x.action,timestamp:x.created_at})))}</div></div>`;
}
async function admin(){
 const [h,u,r,p]=await Promise.all([api("/admin/health"),api("/admin/users"),api("/admin/roles"),api("/admin/permissions")]);
 return pageHead("Administration","Database health, users, roles and permission controls",`<button class="primary" data-backup>Backup Database</button>`)
 +`<div class="grid cards">${metric("Database",h.healthy?"Healthy":"Attention","SQLite health")}${metric("Users",(u.data||[]).length,"Hotel users")}${metric("Roles",(r.data||[]).length,"Configured roles")}${metric("Permissions",(p.data||[]).length,"Active permissions")}</div><div class="grid two" style="margin-top:15px"><div class="card"><h3>Users</h3>${table(u.data||[])}</div><div class="card"><h3>Roles</h3>${table(r.data||[])}</div></div>`;
}
async function renderPage(){
 if(!canOpenPage(state.page)){showAccessDenied();return;}
 document.querySelector(".main-content")?.classList.toggle("room-fullscreen-mode",state.page==="rooms");
 document.getElementById("dashboard-view")?.classList.toggle("room-module-fullscreen",state.page==="rooms");
 document.querySelector(".main-content")?.classList.toggle("guest-fullscreen-mode",state.page==="guests");
 document.getElementById("dashboard-view")?.classList.toggle("guest-module-fullscreen",state.page==="guests");
 const map={dashboard,frontdesk,hotel,mapsmedia,guests,rooms,restaurant,billing,inventory,procurement,hr,expenses,feedback,notifications,transport,reports,audit,admin};
 try{const pageEl=document.getElementById("page");pageEl.setAttribute("aria-busy","true");pageEl.innerHTML=`<div class="loading" role="status" aria-live="polite">Loading…</div>`;pageEl.innerHTML=await map[state.page]();pageEl.setAttribute("aria-busy","false");bindPageEvents();if(state.page==="reports")bindReportEvents();if(state.page==="audit")bindAuditEvents()}catch(e){document.getElementById("page").innerHTML=`<div class="error-box"><strong>Could not load this page.</strong><p>${esc(e.message)}</p><button onclick="render()">Retry</button></div>`}}
function bindAuditEvents(){
 const apply=document.querySelector("[data-audit-filter]"), clear=document.querySelector("[data-audit-clear]");
 if(apply)apply.onclick=()=>render();
 if(clear)clear.onclick=()=>{["audit-search","audit-user","audit-module","audit-action","audit-status","audit-start","audit-end","audit-request"].forEach(id=>{const el=document.getElementById(id);if(el)el.value=""});render()};
 document.querySelectorAll("[data-audit-detail]").forEach(btn=>btn.onclick=async()=>{const row=window.__auditRows?.[Number(btn.dataset.auditDetail)];if(!row)return;alert(JSON.stringify(row,null,2));});
}

function bindReportEvents(){
 const apply=document.querySelector("[data-report-filter]"), clear=document.querySelector("[data-report-clear]");
 if(apply)apply.onclick=()=>render();
 if(clear)clear.onclick=()=>{["report-start","report-end"].forEach(id=>{const el=document.getElementById(id);if(el)el.value=""});render()};
}

function bindExpenseEvents(){
 const apply=document.querySelector("[data-expense-filter]"), clear=document.querySelector("[data-expense-clear]");
 if(apply)apply.onclick=()=>render();
 if(clear)clear.onclick=()=>{["expense-start","expense-end","expense-search","expense-category","expense-payment","expense-approval","expense-recurring"].forEach(id=>{const el=document.getElementById(id);if(el)el.value=""});render()};
}

function bindProcurementEvents(){
 const btn=document.getElementById("supplier-search-btn");
 const input=document.getElementById("supplier-search");
 if(!btn || !input) return;
 const run=async()=>{
  try{ const result=await api("/suppliers/search?q="+encodeURIComponent(input.value.trim())); const target=document.getElementById("supplier-results"); if(target) target.innerHTML=table(result.data||[]); }
  catch(err){ showAccessDenied(err.message||"Unable to search suppliers."); }
 };
 btn.addEventListener("click",run);
 input.addEventListener("keydown",e=>{if(e.key==="Enter") run();});
}

function bindPageEvents(){
 document.querySelectorAll("[data-guest-back-dashboard]").forEach(b=>b.onclick=()=>{state.page="dashboard";render()});
 const p=document.getElementById("page");
 p.querySelectorAll("[data-edit-service-policy]").forEach(btn=>btn.onclick=()=>{
   if(!hasPermission("Settings","Update")){showAccessDenied();return;}
   const row=(window.__guestServicePolicyRows||[]).find(x=>String(x.service_id)===String(btn.dataset.editServicePolicy));
   if(!row)return;
   formModal(`Guest Service Policy — ${row.service_name||"Service"}`,[
     {name:"service_name",label:"Service Name",value:row.service_name},
     {name:"service_type",label:"Service Type",value:row.service_type},
     {name:"price",label:"Default Price (₹)",type:"number",value:Number(row.price||0)},
     {name:"pricing_mode",label:"Pricing Mode",type:"select",options:["Paid","Free","Quote"],value:row.pricing_mode||"Paid"},
     {name:"billing_mode",label:"Billing Mode",type:"select",options:["Reservation Bill","Separate Payment","Free","Quote"],value:row.billing_mode||"Reservation Bill"},
     {name:"assigned_department",label:"Assigned Department",required:false,value:row.assigned_department||""},
     {name:"no_show_policy",label:"No-Show Policy",type:"select",options:["No Charge","Charge If Completed","Cancellation Fee","Full Charge"],value:row.no_show_policy||"No Charge"},
     {name:"cancellation_fee_type",label:"Cancellation Fee Type",type:"select",options:["Fixed","Percent"],value:row.cancellation_fee_type||"Fixed"},
     {name:"cancellation_fee_value",label:"Cancellation Fee Value (₹ or %)",type:"number",value:Number(row.cancellation_fee_value||0)},
     {name:"refund_policy",label:"Refund Policy",type:"select",options:["Refund Paid Amount","No Refund","Manager Approval"],value:row.refund_policy||"Refund Paid Amount"},
     {name:"manager_approval_required",label:"Manager Approval",type:"select",options:["No","Yes"],value:Number(row.manager_approval_required)?"Yes":"No"},
     {name:"is_active",label:"Service Active",type:"select",options:["true","false"],value:Number(row.is_active)?"true":"false"}
   ],async o=>{
     await api(`/guest-services/catalog/${encodeURIComponent(row.service_id)}`,{method:"PATCH",body:JSON.stringify({...o,price:Number(o.price||0),cancellation_fee_value:Number(o.cancellation_fee_value||0),manager_approval_required:o.manager_approval_required==="Yes",is_active:o.is_active==="true"})});
   });
 });
 p.querySelectorAll("[data-page-prev]").forEach(b=>b.onclick=()=>{const key=b.dataset.pagePrev;state.listPages[key]=Math.max(1,Number(state.listPages[key]||1)-1);render()});
 p.querySelectorAll("[data-page-next]").forEach(b=>b.onclick=()=>{const key=b.dataset.pageNext;state.listPages[key]=Number(state.listPages[key]||1)+1;render()});
 p.querySelectorAll("[data-restaurant-detail]").forEach(b=>b.onclick=()=>{const row=(window.__restaurantOrderRows||[])[Number(b.dataset.restaurantDetail)];if(row)showObjectModal(`Restaurant Order ${row.order_id||""}`,row)});
  p.querySelectorAll("[data-restaurant-status]").forEach(b=>b.onclick=()=>{if(!isActionAllowed("order_status")){showAccessDenied();return;}const row=(window.__restaurantOrderRows||[])[Number(b.dataset.restaurantStatus)];if(!row)return;const statuses=["New","Preparing","Ready","Served","Completed","Cancelled"];formModal("Update Restaurant Order Status",[{name:"status",label:"Status",type:"select",options:statuses,value:row.order_status||"New"}],async o=>api(`/restaurant/orders/${encodeURIComponent(row.order_id)}/status`,{method:"PATCH",body:JSON.stringify(o)}));});
 p.querySelector("#restaurant-order-date")?.addEventListener("change",e=>{
    const custom=p.querySelector("#restaurant-order-custom-date");
    if(custom && e.target.value==="custom") custom.focus();
  });
  const applyRestaurantOrderFilters=()=>{
    const q=p.querySelector("#restaurant-order-search")?.value.trim().toLowerCase()||"";
    const st=p.querySelector("#restaurant-order-status")?.value||"";
    const selectedDate=p.querySelector("#restaurant-order-custom-date")?.value||"";
    const selectedDateFilter=p.querySelector("#restaurant-order-date")?.value||"all";
    const dateFilter=selectedDate ? "custom" : selectedDateFilter;
    const customDate=selectedDate;
    if(dateFilter==="custom" && !customDate){
      toast("Select a custom order date first.",true);
      return;
    }
    state.restaurantOrderDateFilter=dateFilter;
    state.restaurantOrderCustomDate=customDate;
    const today=dateNow();
    const tomorrow=addRestaurantOrderDays(today,1);
    const rows=(Array.isArray(window.__allRestaurantOrderRows)?window.__allRestaurantOrderRows:[]).filter(row=>{
      const searchText=[row.order_id,row.customer_name,row.customer_mobile,row.table_number]
        .map(v=>String(v||"").toLowerCase()).join(" ");
      if(q && !searchText.includes(q))return false;
      if(st && String(row.order_status||"")!==st)return false;

      // Always normalize the API date before comparing it. Restaurant APIs may
      // return ISO dates/timestamps or DD-MM-YYYY display dates.
      const orderDate=parseRestaurantOrderDate(row.order_date||row.created_at||row.order_datetime);
      if(dateFilter==="all")return true;
      if(!orderDate)return false;
      if(dateFilter==="today")return orderDate===today;
      if(dateFilter==="tomorrow")return orderDate===tomorrow;
      if(dateFilter==="upcoming")return orderDate>=today;
      if(dateFilter==="past")return orderDate<today;
      if(dateFilter==="custom")return orderDate===customDate;
      return true;
    });
    window.__restaurantOrderRows=rows;
    const actions="<button data-search-order-detail=\"{{i}}\">Details</button>"+(isActionAllowed("order_status")?" <button data-search-order-status=\"{{i}}\">Update Status</button>":"");
    p.querySelector("#restaurant-order-results").innerHTML=`<div class="section-note" style="margin:8px 0 12px">Showing ${rows.length} order(s)</div>${table(rows,actions)}`;
    p.querySelectorAll("[data-search-order-detail]").forEach(b=>b.onclick=()=>{
      const row=rows[Number(b.dataset.searchOrderDetail)];
      if(row)showObjectModal(`Restaurant Order ${row.order_id||""}`,row);
    });
    p.querySelectorAll("[data-search-order-status]").forEach(b=>b.onclick=()=>{
      if(!isActionAllowed("order_status")){showAccessDenied();return;}
      const row=rows[Number(b.dataset.searchOrderStatus)];
      if(!row)return;
      formModal("Update Restaurant Order Status",[{name:"status",label:"Status",type:"select",options:["New","Accepted","Preparing","Ready","Served","Completed","Cancelled"],value:row.order_status||"New"}],async o=>api(`/restaurant/orders/${encodeURIComponent(row.order_id)}/status`,{method:"PATCH",body:JSON.stringify(o)}));
    });
  };

  p.querySelector("#restaurant-order-search-btn")?.addEventListener("click",applyRestaurantOrderFilters);
  p.querySelector("#restaurant-order-custom-date")?.addEventListener("change",e=>{
    const value=e.target.value||"";
    if(value){
      const dateSelect=p.querySelector("#restaurant-order-date");
      if(dateSelect)dateSelect.value="custom";
      state.restaurantOrderDateFilter="custom";
      state.restaurantOrderCustomDate=value;
      applyRestaurantOrderFilters();
    }
  });
  p.querySelector("#restaurant-order-today")?.addEventListener("click",()=>{
    const dateSelect=p.querySelector("#restaurant-order-date");
    const custom=p.querySelector("#restaurant-order-custom-date");
    if(dateSelect)dateSelect.value="today";
    if(custom)custom.value="";
    state.restaurantOrderDateFilter="today";
    state.restaurantOrderCustomDate="";
    applyRestaurantOrderFilters();
  });
  p.querySelector("#restaurant-order-clear")?.addEventListener("click",()=>{
    p.querySelector("#restaurant-order-search").value="";
    p.querySelector("#restaurant-order-status").value="";
    p.querySelector("#restaurant-order-date").value="all";
    const custom=p.querySelector("#restaurant-order-custom-date");
    if(custom)custom.value="";
    state.restaurantOrderDateFilter="all";
    state.restaurantOrderCustomDate="";
    applyRestaurantOrderFilters();
  });
  p.querySelector("[data-table-add]")?.addEventListener("click",()=>{
    if(!isActionAllowed("table_create")){showAccessDenied();return;}
    formModal("Add Restaurant Table",[
      {name:"table_number",label:"Table number",placeholder:"e.g. T9"},
      {name:"table_capacity",label:"Capacity",type:"number",value:2},
      {name:"table_section",label:"Section / Area",value:"Main Dining"}
    ],async o=>api("/tables",{method:"POST",body:JSON.stringify({table_number:o.table_number,table_capacity:Number(o.table_capacity),table_section:o.table_section||"Main Dining"})}));
  });
  p.querySelectorAll("[data-table-edit]").forEach(b=>b.onclick=()=>{
    if(!isActionAllowed("table_status")){showAccessDenied();return;}
    const row=(window.__restaurantTableRows||[])[Number(b.dataset.tableEdit)];
    if(!row)return;
    formModal(`Edit Table ${row.table_number}`,[
      {name:"table_capacity",label:"Capacity",type:"number",value:Number(row.table_capacity||2)},
      {name:"table_section",label:"Section / Area",value:row.table_section||"Main Dining"}
    ],async o=>api(`/tables/${encodeURIComponent(row.table_number)}`,{method:"PATCH",body:JSON.stringify({table_capacity:Number(o.table_capacity),table_section:o.table_section||"Main Dining"})}));
  });
  p.querySelectorAll("[data-table-active]").forEach(b=>b.onclick=async()=>{
    if(!isActionAllowed("table_status")){showAccessDenied();return;}
    const row=(window.__restaurantTableRows||[])[Number(b.dataset.tableActive)];
    if(!row)return;
    const next=Number(row.is_active||0)!==1;
    try{
      await api(`/tables/${encodeURIComponent(row.table_number)}/active`,{method:"PATCH",body:JSON.stringify({is_active:next})});
      toast(`Table ${row.table_number} is now ${next?"Active":"Inactive"}.`);
      render();
    }catch(e){toast(e.message,true)}
  });
  p.querySelectorAll("[data-table-occupy]").forEach(b=>b.onclick=async()=>{
    if(!isActionAllowed("table_status")){showAccessDenied();return;}
    const row=(window.__restaurantTableRows||[])[Number(b.dataset.tableOccupy)];
    if(!row)return;
    try{
      await api(`/tables/${encodeURIComponent(row.table_number)}/occupy`,{method:"PATCH"});
      toast(`Table ${row.table_number} is now Occupied.`);
      render();
    }catch(e){toast(e.message,true)}
  });
  p.querySelectorAll("[data-table-release]").forEach(b=>b.onclick=async()=>{
    if(!isActionAllowed("table_status")){showAccessDenied();return;}
    const row=(window.__restaurantTableRows||[])[Number(b.dataset.tableRelease)];
    if(!row)return;
    try{
      await api(`/tables/${encodeURIComponent(row.table_number)}/release`,{method:"PATCH"});
      toast(`Table ${row.table_number} is now Available.`);
      render();
    }catch(e){toast(e.message,true)}
  });
  p.querySelectorAll("[data-table-clean-start]").forEach(b=>b.onclick=async()=>{
    if(!isActionAllowed("table_status")){showAccessDenied();return;}
    const row=(window.__restaurantTableRows||[])[Number(b.dataset.tableCleanStart)];
    if(!row)return;
    try{
      await api(`/tables/${encodeURIComponent(row.table_number)}/cleaning/start`,{method:"PATCH"});
      toast(`Cleaning started for table ${row.table_number}.`);
      render();
    }catch(e){toast(e.message,true)}
  });
  p.querySelectorAll("[data-table-clean-complete]").forEach(b=>b.onclick=async()=>{
    if(!isActionAllowed("table_status")){showAccessDenied();return;}
    const row=(window.__restaurantTableRows||[])[Number(b.dataset.tableCleanComplete)];
    if(!row)return;
    try{
      await api(`/tables/${encodeURIComponent(row.table_number)}/cleaning/complete`,{method:"PATCH"});
      toast(`Table ${row.table_number} is now Available.`);
      render();
    }catch(e){toast(e.message,true)}
  });
  p.querySelector("[data-menu-add-category]")?.addEventListener("click",()=>{
    if(!isActionAllowed("restaurant_menu_create")){showAccessDenied();return;}
    formModal("Add Menu Category",[
      {name:"category_name",label:"Category name",placeholder:"e.g. Breakfast"}
    ],async o=>{
      await api("/restaurant/menu/categories",{method:"POST",body:JSON.stringify(o)});
    });
  });
  p.querySelector("[data-menu-add]")?.addEventListener("click",()=>{
    if(!isActionAllowed("restaurant_menu_create")){showAccessDenied();return;}
    const categories=window.__restaurantMenuCategories||[];
    if(!categories.length){toast("Add a menu category first.",true);return;}
    const options=categories.map(c=>`${c.category_id} — ${c.category_name}`);
    formModal("Add Restaurant Menu Item",[
      {name:"item_name",label:"Item name",placeholder:"e.g. Tea"},
      {name:"price",label:"Price (₹)",type:"number",placeholder:"0",value:"0"},
      {name:"category",label:"Category",type:"select",options},
      {name:"description",label:"Description",required:false,placeholder:"Optional description"}
    ],async o=>{
      const category_id=String(o.category||"").split(" — ")[0];
      await api("/restaurant/menu",{method:"POST",body:JSON.stringify({
        item_name:o.item_name,price:Number(o.price||0),category_id,description:o.description||""
      })});
    });
  });
  p.querySelectorAll("[data-menu-edit]").forEach(b=>b.onclick=()=>{
    if(!isActionAllowed("restaurant_menu_update")){showAccessDenied();return;}
    const row=(window.__restaurantMenuRows||[])[Number(b.dataset.menuEdit)];
    if(!row)return;
    const categories=window.__restaurantMenuCategories||[];
    const options=categories.map(c=>`${c.category_id} — ${c.category_name}`);
    const currentCategory=`${row.category_id} — ${row.category_name}`;
    formModal(`Edit Menu Item ${row.item_id}` ,[
      {name:"item_name",label:"Item name",value:row.item_name},
      {name:"price",label:"Price (₹)",type:"number",value:row.price},
      {name:"category",label:"Category",type:"select",options,value:currentCategory},
      {name:"description",label:"Description",required:false,value:row.description||""}
    ],async o=>{
      const category_id=String(o.category||"").split(" — ")[0];
      await api(`/restaurant/menu/${encodeURIComponent(row.item_id)}`,{method:"PATCH",body:JSON.stringify({
        item_name:o.item_name,price:Number(o.price||0),category_id,description:o.description||""
      })});
    });
  });
  p.querySelectorAll("[data-menu-availability]").forEach(b=>b.onclick=async()=>{
    if(!isActionAllowed("restaurant_menu_update")){showAccessDenied();return;}
    const row=(window.__restaurantMenuRows||[])[Number(b.dataset.menuAvailability)];
    if(!row)return;
    const next=!Boolean(Number(row.is_available));
    const label=next?"activate":"deactivate";
    if(!window.confirm(`Are you sure you want to ${label} ${row.item_name}?`))return;
    try{
      await api(`/restaurant/menu/${encodeURIComponent(row.item_id)}/availability`,{
        method:"PATCH",body:JSON.stringify({is_available:next})
      });
      toast(`Menu item ${next?"activated":"deactivated"}.`);
      render();
    }catch(e){toast(e.message,true);}
  });


 p.querySelector("[data-feedback-filter]")?.addEventListener("click",()=>{state.feedbackSearch=p.querySelector("#feedback-search")?.value.trim()||"";state.feedbackCategory=p.querySelector("#feedback-category")?.value||"";state.feedbackRating=p.querySelector("#feedback-rating")?.value||"";state.feedbackStatus=p.querySelector("#feedback-status")?.value||"";state.feedbackComplaints=p.querySelector("#feedback-complaints")?.value||"";state.feedbackFollow=p.querySelector("#feedback-follow")?.value||"";render()});
 p.querySelector("[data-feedback-clear]")?.addEventListener("click",()=>{state.feedbackSearch=state.feedbackCategory=state.feedbackRating=state.feedbackStatus=state.feedbackComplaints=state.feedbackFollow="";render()});
 p.querySelectorAll("[data-feedback-manage],[data-complaint-manage]").forEach(b=>b.onclick=()=>{if(!isActionAllowed("feedback_update")){showAccessDenied();return;}const isComplaint=b.dataset.complaintManage!==undefined;const row=(isComplaint?window.__complaintRows:window.__feedbackRows||[])[Number(isComplaint?b.dataset.complaintManage:b.dataset.feedbackManage)];if(!row)return;formModal(`Manage Feedback ${row.feedback_id}`,[{name:"rating",label:"Rating",type:"number",value:row.rating||5},{name:"review",label:"Review",value:row.feedback||"",full:true},{name:"category",label:"Category",type:"select",options:["General","Room","Restaurant","Cleanliness","Staff","Service","Facilities","Billing","Other"],value:row.category||"General"},{name:"complaint",label:"Complaint",required:false,value:row.complaint||"",full:true},{name:"issue",label:"Issue",required:false,value:row.issue||"",full:true},{name:"resolution",label:"Resolution",required:false,value:row.resolution||"",full:true},{name:"status",label:"Status",type:"select",options:["Open","In Progress","Resolved","Closed"],value:row.status||"Closed"},{name:"follow_up_required",label:"Follow-up Required",type:"select",options:["false","true"],value:Number(row.follow_up_required||0)?"true":"false"},{name:"follow_up_date",label:"Follow-up Date (DD-MM-YYYY)",required:false,value:row.follow_up_date||""},{name:"follow_up_method",label:"Follow-up Method",type:"select",options:["","Call","WhatsApp","Email"],required:false,value:row.follow_up_method||""},{name:"follow_up_status",label:"Follow-up Status",type:"select",options:["","Pending","Completed"],required:false,value:row.follow_up_status||""},{name:"follow_up_notes",label:"Follow-up Notes",required:false,value:row.follow_up_notes||"",full:true}],o=>api(`/feedback/${encodeURIComponent(row.feedback_id)}`,{method:"PATCH",body:JSON.stringify({...o,rating:Number(o.rating),follow_up_required:String(o.follow_up_required).toLowerCase()==="true",allow_pending_complaint:true})}));});

 p.querySelector("[data-notification-filter]")?.addEventListener("click",()=>render());
 p.querySelector("[data-notification-clear]")?.addEventListener("click",()=>{state.page="notifications";render()});
 p.querySelector("#notification-search")?.addEventListener("keydown",e=>{if(e.key==="Enter")render()});
 p.querySelector("#inventory-search-btn")?.addEventListener("click",()=>{state.inventorySearch=p.querySelector("#inventory-search")?.value.trim()||"";render()});
 p.querySelector("#inventory-clear")?.addEventListener("click",()=>{state.inventorySearch="";render()});
 p.querySelectorAll("[data-inv-stock]").forEach(b=>b.onclick=()=>{if(!isActionAllowed("inventory_stock")){showAccessDenied();return;}const row=(window.__inventoryItems||[])[Number(b.dataset.invStock)];if(!row)return;formModal(`Stock Movement - ${row.item_id}`,[{name:"movement",label:"Movement",type:"select",options:["Stock In","Stock Out","Adjustment Increase","Adjustment Decrease","Damaged"]},{name:"quantity",label:"Quantity",type:"number",placeholder:"Required"},{name:"reason",label:"Reason"},{name:"reference_no",label:"Reference No"}],async o=>{const qty=Number(o.quantity||0);if(qty<=0)throw new Error("Quantity must be greater than zero.");let path="/inventory/stock-in",body={item_id:row.item_id,quantity:qty,reason:o.reason,reference_no:o.reference_no};if(o.movement==="Stock Out")path="/inventory/stock-out";else if(o.movement==="Adjustment Increase"||o.movement==="Adjustment Decrease"){path="/inventory/adjustment";body={item_id:row.item_id,adjustment_type:o.movement.endsWith("Increase")?"INCREASE":"DECREASE",quantity:qty,reason:o.reason,reference_no:o.reference_no};}else if(o.movement==="Damaged")path="/inventory/damaged";await api(path,{method:"POST",body:JSON.stringify(body)});toast("Inventory movement saved.");render()});});
 p.querySelector("[data-user-create]")?.addEventListener("click",()=>{
   if(!hasPermission("Users","Create")){showAccessDenied();return;}
   const roles=window.__hrUserRoles||[];
   formModal("Create Login User",[
     {name:"user_id",label:"User ID",placeholder:"e.g. KITCHEN01"},
     {name:"username",label:"Login Username",placeholder:"e.g. kitchen_test"},
     {name:"password",label:"Password",type:"password",placeholder:"Minimum 8 characters"},
     {name:"role",label:"Role",type:"select",options:roles},
     {name:"staff_id",label:"Staff ID (optional)",required:false,placeholder:"Link existing staff only"},
     {name:"reason",label:"Reason",value:"Role-based login account created from Staff & HR.",full:true}
   ],async o=>{
     await api("/admin/users",{method:"POST",body:JSON.stringify({
       user_id:o.user_id,username:o.username,password:o.password,role:o.role,
       staff_id:o.staff_id||null,reason:o.reason
     })});
     toast("Login user created successfully.");
     render();
   });
 });
 p.querySelectorAll("[data-action]").forEach(b=>{if(!isActionAllowed(b.dataset.action)){b.remove();return;}b.onclick=()=>openAction(b.dataset.action)});
 p.querySelector("[data-refresh]")?.addEventListener("click",render);
 p.querySelector("[data-backup]")?.addEventListener("click",async()=>{if(!isActionAllowed("backup")){showAccessDenied();return;}try{const r=await api("/admin/backup",{method:"POST"});toast("Backup created.");console.log(r)}catch(e){toast(e.message,true)}});
 p.querySelector("#do-search")?.addEventListener("click",()=>{const q=p.querySelector("#page-search").value.trim();state.search=q;render()}); p.querySelector("#billing-search-btn")?.addEventListener("click",()=>{state.search=p.querySelector("#billing-search")?.value.trim()||"";render()});
 p.querySelector("#billing-clear")?.addEventListener("click",()=>{state.search="";render()});
 p.querySelectorAll("[data-invoice-detail]").forEach(b=>b.onclick=async()=>{const rows=(await api(`/billing/invoices${state.search?`?search=${encodeURIComponent(state.search)}`:""}`)).data||[];const row=rows[Number(b.dataset.invoiceDetail)];if(!row)return;try{const d=(await api(`/billing/invoices/${encodeURIComponent(row.invoice_number)}`)).data;showObjectModal("Invoice Details",d)}catch(e){toast(e.message,true)}});

 p.querySelector("#clear-search")?.addEventListener("click",()=>{state.search="";render()});
 p.querySelectorAll(".guest-date-input").forEach(input=>input.addEventListener("change",()=>{input.classList.toggle("guest-date-empty",!input.value)}));
 p.querySelector("#guest-search-btn")?.addEventListener("click",()=>{const dateFrom=p.querySelector("#guest-date-from")?.value||"";const dateTo=p.querySelector("#guest-date-to")?.value||"";state.guestSearch=p.querySelector("#guest-search")?.value||"";state.guestSearchField=p.querySelector("#guest-search-field")?.value||"all";state.guestStatus=p.querySelector("#guest-status-filter")?.value||"";state.guestDateType="created";state.guestDateFrom=dateFrom;state.guestDateTo=dateTo;render()});
 p.querySelector("#guest-clear-btn")?.addEventListener("click",()=>{state.guestSearch="";state.guestSearchField="all";state.guestStatus="";state.guestDateType="created";state.guestDateFrom="";state.guestDateTo="";render()});
 p.querySelectorAll("[data-guest-detail]").forEach(b=>b.onclick=async()=>{const rows=(await api((()=>{const q=new URLSearchParams({search_field:state.guestSearchField||"all",date_type:"created"}); if(state.guestSearch)q.set("search",state.guestSearch); if(state.guestStatus)q.set("guest_status",state.guestStatus); if(state.guestDateFrom)q.set("date_from",state.guestDateFrom); if(state.guestDateTo)q.set("date_to",state.guestDateTo); return "/customers?"+q.toString()})())).data||[];const row=rows[Number(b.dataset.guestDetail)];if(!row)return;try{document.getElementById("page").innerHTML=`<div class="loading">Loading guest…</div>`;document.getElementById("page").innerHTML=await guestDetail(row.customer_id);bindPageEvents()}catch(e){document.getElementById("page").innerHTML=`<div class="error-box">${esc(e.message)}</div>`}});
 p.querySelectorAll("[data-guest-edit]").forEach(b=>b.onclick=async()=>{const rows=(await api((()=>{const q=new URLSearchParams({search_field:state.guestSearchField||"all",date_type:"created"}); if(state.guestSearch)q.set("search",state.guestSearch); if(state.guestStatus)q.set("guest_status",state.guestStatus); if(state.guestDateFrom)q.set("date_from",state.guestDateFrom); if(state.guestDateTo)q.set("date_to",state.guestDateTo); return "/customers?"+q.toString()})())).data||[];const row=rows[Number(b.dataset.guestEdit)];if(row)openGuestEdit(row)});
 p.querySelectorAll("[data-guest-status-action]").forEach(b=>b.addEventListener("click",()=>changeGuestStatus(b.dataset.customerId,b.dataset.guestStatusAction)));
 p.querySelector("[data-back-guests]")?.addEventListener("click",()=>render());
 p.querySelector("[data-edit-current]")?.addEventListener("click",async e=>{const r=(await api(`/customers/${encodeURIComponent(e.currentTarget.dataset.editCurrent)}`)).data;openGuestEdit(r.customer)});
 p.querySelectorAll("[data-guest-section]").forEach(tab=>tab.addEventListener("click",()=>{
   const key=tab.dataset.guestSection;
   const panel=p.querySelector(`[data-guest-panel="${key}"]`);
   const wasOpen=tab.getAttribute("aria-expanded")==="true";
   p.querySelectorAll("[data-guest-section]").forEach(t=>t.setAttribute("aria-expanded","false"));
   p.querySelectorAll("[data-guest-panel]").forEach(x=>x.hidden=true);
   if(!wasOpen&&panel){tab.setAttribute("aria-expanded","true");panel.hidden=false;}
 }));
 p.querySelector("[data-map-config]")?.addEventListener("click",async()=>{const r=await api("/hotel/maps"),c=r.data?.configuration||{};formModal("Map Configuration",[{name:"provider",label:"Provider",type:"select",options:["Google Maps","OpenStreetMap","Apple Maps"],value:c.map_provider||"Google Maps"},{name:"latitude",label:"Latitude",type:"number",required:false,value:c.latitude??""},{name:"longitude",label:"Longitude",type:"number",required:false,value:c.longitude??""},{name:"default_zoom",label:"Default zoom",type:"number",value:c.default_zoom||16},{name:"api_enabled",label:"API enabled",type:"select",options:["false","true"],value:String(Boolean(c.api_enabled))},{name:"integration_status",label:"Integration status",type:"select",options:["Not Integrated","Pending Integration","Integrated","Failed"],value:c.integration_status||"Not Integrated"}],o=>api("/hotel/maps/configuration",{method:"PUT",body:JSON.stringify({...o,latitude:o.latitude?Number(o.latitude):null,longitude:o.longitude?Number(o.longitude):null,default_zoom:Number(o.default_zoom),api_enabled:o.api_enabled==="true"})}))});
p.querySelector("[data-nearby-create]")?.addEventListener("click",()=>formModal("Add Nearby Place",[{name:"place_name",label:"Place name"},{name:"category",label:"Category"},{name:"address",label:"Address",required:false},{name:"distance_km",label:"Distance (km)",type:"number",required:false},{name:"travel_time_minutes",label:"Travel time (minutes)",type:"number",required:false},{name:"latitude",label:"Latitude",type:"number",required:false},{name:"longitude",label:"Longitude",type:"number",required:false},{name:"notes",label:"Notes",required:false,full:true}],o=>api("/hotel/nearby-places",{method:"POST",body:JSON.stringify({...o,distance_km:o.distance_km?Number(o.distance_km):null,travel_time_minutes:o.travel_time_minutes?Number(o.travel_time_minutes):null,latitude:o.latitude?Number(o.latitude):null,longitude:o.longitude?Number(o.longitude):null})})));
p.querySelector("[data-route-create]")?.addEventListener("click",()=>formModal("Create Navigation Route",[{name:"origin",label:"Origin"},{name:"destination",label:"Destination"},{name:"distance_km",label:"Distance (km)",type:"number",required:false},{name:"eta_minutes",label:"ETA (minutes)",type:"number",required:false},{name:"provider",label:"Provider",type:"select",options:["Google Maps","OpenStreetMap","Apple Maps"],required:false},{name:"integration_status",label:"Integration status",type:"select",options:["Not Integrated","Pending Integration","Integrated","Failed"]},{name:"notes",label:"Notes",required:false,full:true}],o=>api("/hotel/navigation-routes",{method:"POST",body:JSON.stringify({...o,distance_km:o.distance_km?Number(o.distance_km):null,eta_minutes:o.eta_minutes?Number(o.eta_minutes):null,provider:o.provider||null})})));
p.querySelector("[data-media-create]")?.addEventListener("click",()=>formModal("Add Media",[{name:"category",label:"Category",type:"select",options:["Hotel","Room","Restaurant","Banquet","Facility","Event","Food","Other"]},{name:"media_type",label:"Media type",type:"select",options:["Image","Video","Other"]},{name:"title",label:"Title"},{name:"file_url",label:"File / URL"},{name:"description",label:"Description",required:false,full:true},{name:"display_order",label:"Display order",type:"number",value:1},{name:"guest_visible",label:"Guest visible",type:"select",options:["true","false"],value:"true"}],o=>api("/hotel/media",{method:"POST",body:JSON.stringify({...o,display_order:Number(o.display_order),guest_visible:o.guest_visible==="true"})})));
p.querySelectorAll("[data-nearby-status]").forEach(b=>b.onclick=()=>{const row=window.__nearbyRows?.[Number(b.dataset.nearbyStatus)];if(!row)return;formModal("Nearby Place Status",[{name:"is_active",label:"Status",type:"select",options:["true","false"],value:String(Boolean(row.is_active))}],o=>api(`/hotel/nearby-places/${row.place_id}/status`,{method:"PATCH",body:JSON.stringify({is_active:o.is_active==="true"})}))});
p.querySelectorAll("[data-media-status]").forEach(b=>b.onclick=()=>{const row=window.__mediaRows?.[Number(b.dataset.mediaStatus)];if(!row)return;formModal("Media Status",[{name:"status",label:"Status",type:"select",options:["Active","Inactive"],value:row.is_active?"Active":"Inactive"}],o=>api(`/hotel/media/${encodeURIComponent(row.media_id)}/status`,{method:"PATCH",body:JSON.stringify(o)}))});
p.querySelectorAll("[data-media-edit]").forEach(b=>b.onclick=()=>{const row=window.__mediaRows?.[Number(b.dataset.mediaEdit)];if(!row)return;formModal("Edit Media",[{name:"category",label:"Category",type:"select",options:["Hotel","Room","Restaurant","Banquet","Facility","Event","Food","Other"],value:row.category},{name:"media_type",label:"Media type",type:"select",options:["Image","Video","Other"],value:row.media_type},{name:"title",label:"Title",value:row.title},{name:"file_url",label:"File / URL",value:row.media_reference},{name:"description",label:"Description",required:false,value:row.description||"",full:true},{name:"display_order",label:"Display order",type:"number",value:row.display_order||1},{name:"guest_visible",label:"Guest visible",type:"select",options:["true","false"],value:String(Boolean(row.is_guest_visible))}],o=>api(`/hotel/media/${encodeURIComponent(row.media_id)}`,{method:"PUT",body:JSON.stringify({...o,display_order:Number(o.display_order),guest_visible:o.guest_visible==="true"})}))});
p.querySelector("[data-transport-filter]")?.addEventListener("click",()=>{state.transportSearch=p.querySelector("#transport-search")?.value.trim()||"";state.transportStatus=p.querySelector("#transport-status")?.value||"";state.transportIntegration=p.querySelector("#transport-integration")?.value||"";render()});
 p.querySelector("[data-transport-clear]")?.addEventListener("click",()=>{state.transportSearch=state.transportStatus=state.transportIntegration="";render()});
 p.querySelectorAll("[data-transport-detail]").forEach(b=>b.onclick=()=>{const row=window.__transportRows?.[Number(b.dataset.transportDetail)];if(row)showObjectModal(`Transportation Request ${row.request_id||""}`,row)});
 p.querySelectorAll("[data-transport-edit]").forEach(b=>b.onclick=()=>{if(!isActionAllowed("transport_update")){showAccessDenied();return;}const row=window.__transportRows?.[Number(b.dataset.transportEdit)];if(!row)return;formModal(`Manage Transportation ${row.request_id||""}`,[{name:"status",label:"Status",type:"select",options:["Requested","Confirmed","Assigned","Driver On The Way","In Transit","Completed","Cancelled","No-Show"],value:row.status||"Requested"},{name:"vehicle_id",label:"Vehicle ID",required:false,value:row.vehicle_id||""},{name:"driver_id",label:"Driver ID",required:false,value:row.driver_id||""},{name:"fare",label:"Fare",type:"number",required:false,value:row.fare||0},{name:"provider_name",label:"Provider",required:false,value:row.provider_name||""},{name:"provider_reference",label:"Provider Reference",required:false,value:row.provider_reference||""},{name:"integration_status",label:"Integration Status",type:"select",options:["Not Integrated","Pending Integration","Integrated","Failed"],value:row.integration_status||"Not Integrated"},{name:"special_request",label:"Special Request",required:false,value:row.special_request||"",full:true},{name:"notes",label:"Notes",required:false,value:row.notes||"",full:true}],o=>api(`/transportation/requests/${encodeURIComponent(row.request_id)}`,{method:"PATCH",body:JSON.stringify({...o,fare:o.fare===undefined?undefined:Number(o.fare)})}))});
 p.querySelectorAll("[data-vehicle-status]").forEach(b=>b.onclick=()=>{if(!isActionAllowed("transport_update")){showAccessDenied();return;}const row=window.__vehicleRows?.[Number(b.dataset.vehicleStatus)];if(!row)return;formModal(`Vehicle Status ${row.vehicle_id||""}`,[{name:"status",label:"Status",type:"select",options:["Active","Inactive"],value:row.status||"Active"}],o=>api(`/transportation/vehicles/${encodeURIComponent(row.vehicle_id)}/status`,{method:"PATCH",body:JSON.stringify(o)}))});
 p.querySelectorAll("[data-driver-status]").forEach(b=>b.onclick=()=>{if(!isActionAllowed("transport_update")){showAccessDenied();return;}const row=window.__driverRows?.[Number(b.dataset.driverStatus)];if(!row)return;formModal(`Driver Status ${row.driver_id||""}`,[{name:"status",label:"Status",type:"select",options:["Active","Inactive"],value:row.status||"Active"}],o=>api(`/transportation/drivers/${encodeURIComponent(row.driver_id)}/status`,{method:"PATCH",body:JSON.stringify(o)}))});
 p.querySelectorAll("[data-read]").forEach(b=>b.onclick=async()=>{if(!isActionAllowed("notification_read")){showAccessDenied();return;}const rows=window.__notificationRows||[];const row=rows[Number(b.dataset.read)];if(row?.delivery_id){try{await api(`/notifications/${encodeURIComponent(row.delivery_id)}/read`,{method:"POST",body:"{}"});toast("Notification marked read.");render()}catch(e){toast(e.message,true)}}});
 p.querySelectorAll("[data-room-section]").forEach(b=>{const open=()=>{const section=b.dataset.roomSection||"overview";state.roomSection=section;if(section==="booked")state.roomAvailabilityDate=dateNow();render()};b.onclick=open;b.onkeydown=e=>{if(e.key==="Enter"||e.key===" "){e.preventDefault();open()}}});
 p.querySelectorAll("[data-room-home]").forEach(b=>b.onclick=()=>{state.roomSection="overview";render()});
 p.querySelector("[data-room-notifications]")?.addEventListener("click",()=>document.getElementById("notification-btn")?.click());
 p.querySelector("[data-room-profile]")?.addEventListener("click",()=>document.getElementById("user-btn")?.click());
 p.querySelectorAll("[data-restaurant-section]").forEach(b=>b.onclick=()=>{state.restaurantSection=b.dataset.restaurantSection||"overview";render()});
 p.querySelectorAll("[data-kitchen-summary]").forEach(b=>{const toggle=()=>{const key=b.dataset.kitchenSummary||"";state.kitchenSummaryOpen=state.kitchenSummaryOpen===key?"":key;render()};b.onclick=toggle;b.onkeydown=e=>{if(e.key==="Enter"||e.key===" "){e.preventDefault();toggle()}}});
 p.querySelector("[data-kitchen-summary-close]")?.addEventListener("click",()=>{state.kitchenSummaryOpen="";render()});
 p.querySelector("#restaurant-kitchen-status")?.addEventListener("change",e=>{state.restaurantKitchenStatus=e.target.value||"all";render()});
 p.querySelector("#restaurant-kitchen-clear")?.addEventListener("click",()=>{state.restaurantKitchenStatus="all";render()});
 p.querySelectorAll("[data-kitchen-detail]").forEach(b=>b.onclick=()=>{const row=(window.__restaurantKitchenRows||[])[Number(b.dataset.kitchenDetail)];if(row)restaurantKitchenDetailModal(row)});
 p.querySelectorAll("[data-kitchen-accept],[data-kitchen-prepare],[data-kitchen-ready]").forEach(b=>b.onclick=async()=>{
   if(!isActionAllowed("order_status")){showAccessDenied();return;}
   const id=b.dataset.kitchenAccept||b.dataset.kitchenPrepare||b.dataset.kitchenReady;
   const next=b.dataset.kitchenAccept?"Accepted":b.dataset.kitchenPrepare?"Preparing":"Ready";
   try{await api(`/restaurant/orders/${encodeURIComponent(id)}/status`,{method:"PATCH",body:JSON.stringify({status:next})});toast(`Order ${id} moved to ${next}.`);render();}catch(e){toast(e.message,true)}
 });
 p.querySelectorAll("[data-kitchen-detail]").forEach(b=>b.onclick=async()=>{
   const id=b.dataset.kitchenDetail;
   const row=(window.__restaurantKitchenRows||[]).find(r=>String(r.order_id)===String(id));
   if(row)restaurantKitchenDetailModal(row);
 });
 p.querySelectorAll("[data-kitchen-unavailable]").forEach(b=>b.onclick=()=>{
   if(!isActionAllowed("order_status")){showAccessDenied();return;}
   const row=(window.__restaurantMenuRows||[])[Number(b.dataset.kitchenUnavailable)]; if(!row)return;
   formModal(`Mark ${row.item_name||"Item"} Unavailable`,[{name:"reason",label:"Reason",required:false,placeholder:"e.g. Ingredient unavailable",full:true}],async o=>api(`/restaurant/menu/${encodeURIComponent(row.item_id)}/availability`,{method:"PATCH",body:JSON.stringify({is_available:false,reason:o.reason||""})}));
 });
 p.querySelectorAll("[data-kitchen-available]").forEach(b=>b.onclick=async()=>{
   if(!isActionAllowed("order_status")){showAccessDenied();return;}
   const row=(window.__restaurantMenuRows||[])[Number(b.dataset.kitchenAvailable)]; if(!row)return;
   try{await api(`/restaurant/menu/${encodeURIComponent(row.item_id)}/availability`,{method:"PATCH",body:JSON.stringify({is_available:true,reason:""})});toast(`${row.item_name||"Item"} is now available.`);render();}catch(e){toast(e.message,true)}
 });
 p.querySelector("[data-kitchen-request-new]")?.addEventListener("click",()=>{
   if(!isActionAllowed("order_status")){showAccessDenied();return;}
   formModal("New Kitchen Request",[{name:"request_type",label:"Request type",type:"select",options:["Gas/Cylinder","Plates","Glasses","Cutlery","Ingredient","Equipment","Cleaning Material","Other"]},{name:"title",label:"Request",placeholder:"e.g. Gas cylinder required"},{name:"description",label:"Details",required:false,full:true},{name:"priority",label:"Priority",type:"select",options:["Low","Normal","High","Urgent"],value:"Normal"}],async o=>api("/kitchen/requests",{method:"POST",body:JSON.stringify(o)}));
 });
 p.querySelectorAll("[data-kitchen-request-status]").forEach(b=>b.onclick=()=>{
   if(!isActionAllowed("order_status")){showAccessDenied();return;}
   const row=(window.__kitchenRequestRows||[])[Number(b.dataset.kitchenRequestStatus)]; if(!row)return;
   formModal(`Kitchen Request ${row.request_id||""}`,[{name:"status",label:"Status",type:"select",options:["Pending","In Progress","Completed","Cancelled"],value:row.status||"Pending"}],async o=>api(`/kitchen/requests/${encodeURIComponent(row.request_id)}/status`,{method:"PATCH",body:JSON.stringify(o)}));
 });
 p.querySelectorAll("[data-kitchen-next]").forEach(b=>b.onclick=async()=>{
   if(!isActionAllowed("order_status")){showAccessDenied();return;}
   const row=(window.__restaurantKitchenRows||[])[Number(b.dataset.kitchenNext)];
   if(!row)return;
   const current=String(row.order_status||"New");
   const next={New:"Accepted",Accepted:"Preparing",Preparing:"Ready"}[current];
   if(!next)return;
   try{
     await api(`/restaurant/orders/${encodeURIComponent(row.order_id)}/status`,{method:"PATCH",body:JSON.stringify({status:next})});
     toast(`Order ${row.order_id||""} moved to ${next}.`);
     render();
   }catch(e){toast(e.message,true)}
 });
 p.querySelectorAll("[data-room-detail]").forEach(b=>b.onclick=async()=>{const rows=(await api("/rooms")).data||[];const row=rows[Number(b.dataset.roomDetail)];if(row)showObjectModal("Room Details",row)});
 p.querySelectorAll("[data-room-edit]").forEach(b=>b.onclick=async()=>{
  if(!isActionAllowed("room_update")){
    showAccessDenied();
    return;
  }

  const rows=(await api("/rooms")).data||[];
  const row=rows[Number(b.dataset.roomEdit)];

  if(!row)return;

  formModal("Edit Room",[
    {name:"room_type",label:"Room type",value:row.room_type||""},
    {name:"floor",label:"Floor",type:"number",value:row.floor||1},
    {name:"capacity",label:"Capacity",type:"number",value:row.capacity||1},
    {name:"room_price",label:"Room price",type:"number",value:row.room_price||0},
    {name:"amenities",label:"Amenities",required:false,value:row.amenities||"",full:true},
    {name:"description",label:"Description",required:false,value:row.description||"",full:true}
  ],o=>api(`/rooms/${encodeURIComponent(row.room_number)}`,{
    method:"PATCH",
    body:JSON.stringify({
      room_type:o.room_type,
      floor:Number(o.floor),
      capacity:Number(o.capacity),
      room_price:Number(o.room_price),
      amenities:o.amenities||"",
      description:o.description||""
    })
  }));
});
p.querySelectorAll("[data-room-status]").forEach(b=>b.onclick=async()=>{
  if(!isActionAllowed("room_update")){
    showAccessDenied();
    return;
  }

  const rows=(await api("/rooms")).data||[];
  const row=rows[Number(b.dataset.roomStatus)];

  if(!row)return;

  formModal("Change Room Status",[
    {
      name:"room_status",
      label:"Room status",
      type:"select",
      options:[
        "Available",
        "Reserved",
        "Occupied",
        "Maintenance",
        "Out of Service"
      ],
      value:row.room_status||"Available"
    }
  ],o=>api(`/rooms/${encodeURIComponent(row.room_number)}/status`,{
    method:"PATCH",
    body:JSON.stringify({
      room_status:o.room_status
    })
  }));
});
p.querySelectorAll("[data-room-active]").forEach(b=>b.onclick=async()=>{
  if(!isActionAllowed("room_update")){
    showAccessDenied();
    return;
  }

  const rows=(await api("/rooms?active_only=false")).data||[];
  const row=rows[Number(b.dataset.roomActive)];

  if(!row)return;

  const currentlyActive =
    row.is_active === true ||
    Number(row.is_active) === 1;

  const nextActive=!currentlyActive;

  formModal(
    nextActive ? "Activate Room" : "Deactivate Room",
    [
      {
        name:"is_active",
        label:"Status",
        type:"select",
        options:["true","false"],
        value:String(nextActive)
      }
    ],
    o=>api(`/rooms/${encodeURIComponent(row.room_number)}/active-status`,{
      method:"PATCH",
      body:JSON.stringify({
        is_active:o.is_active==="true"
      })
    })
  );
});
 p.querySelectorAll("[data-occupied-room-view]").forEach(b=>b.onclick=async()=>{
   const roomNumber=b.dataset.occupiedRoomView||"";
   if(!roomNumber)return;
   try{
     const row=(await api(`/rooms/${encodeURIComponent(roomNumber)}`)).data||null;
     if(row)showObjectModal("Room Details",row);
   }catch(e){toast(e.message||"Could not load room details.",true);}
 });
 p.querySelectorAll("[data-occupied-action]").forEach(b=>b.onclick=async()=>{
   const action=b.dataset.occupiedAction;
   const bookingId=b.dataset.bookingId||"";
   const roomNumber=b.dataset.roomNumber||"";
   b.closest("details")?.removeAttribute("open");
   try{
     if(action==="check-out"){
       if(!bookingId) throw new Error("Active reservation was not found.");
       return reservationAction("check-out",bookingId);
     }
     if(action==="late-check-out"){
       if(!bookingId) throw new Error("Active reservation was not found.");
       return reservationAction("stay-options",bookingId);
     }
     if(action==="transfer-room"){
       if(!bookingId) throw new Error("Active reservation was not found.");
       return reservationAction("transfer",bookingId);
     }
     if(action==="guest-service"){
       if(!bookingId) throw new Error("Active reservation was not found.");
       state.page="rooms";
       document.getElementById("page").innerHTML=`<div class="loading">Loading reservation…</div>`;
       document.getElementById("page").innerHTML=await reservationDetail(bookingId);
       bindPageEvents();
       return;
     }
     if(action==="need-housekeeping"){
       toast("Housekeeping request action is ready for the next step.",false);
       return;
     }
     if(action==="maintenance"){
       if(!roomNumber) throw new Error("Room number was not found.");
       if(!isActionAllowed("room_update")){showAccessDenied();return;}
       return formModal("Room Maintenance",[
         {name:"room_status",label:"Room status",type:"select",options:["Maintenance","Out of Service"],value:"Maintenance"}
       ],async o=>{
         const result=await api(`/rooms/${encodeURIComponent(roomNumber)}/status`,{
           method:"PATCH",
           body:JSON.stringify({room_status:o.room_status})
         });
         toast(result?.message||`Room ${roomNumber} status updated.`);
         await render();
       });
     }
   }catch(e){toast(e.message||"Occupied room action failed.",true);}
 });
 p.querySelectorAll("[data-booked-room-action]").forEach(b=>b.onclick=()=>openBookedRoomActionMenu(b.dataset.bookedRoomAction));
 p.querySelectorAll("[data-reservation-detail-id]").forEach(b=>b.onclick=async()=>{try{const bookingId=b.dataset.reservationDetailId;if(!bookingId)throw new Error("Reservation record was not found.");state.page="rooms";document.getElementById("page").innerHTML=`<div class="loading">Loading reservation…</div>`;document.getElementById("page").innerHTML=await reservationDetail(bookingId);bindPageEvents()}catch(e){document.getElementById("page").innerHTML=`<div class="error-box"><h3>Could not load reservation</h3><p>${esc(e?.message||"Unknown error")}</p><button data-back-rooms>Back to Rooms & Reservations</button></div>`;document.getElementById("page").querySelector("[data-back-rooms]")?.addEventListener("click",()=>render())}});
 p.querySelectorAll("[data-reservation-edit-id]").forEach(b=>b.onclick=async()=>{const bookingId=b.dataset.reservationEditId;if(!bookingId)return;const row=(await api(`/room-bookings?booking_id=${encodeURIComponent(bookingId)}`)).data||null;if(row)openReservationEdit(row);});
 p.querySelector("#room-reservation-search")?.addEventListener("keydown",e=>{if(e.key==="Enter"){state.roomReservationSearch=e.target.value;render()}});  p.querySelector("#room-reservation-search-btn")?.addEventListener("click",()=>{state.roomReservationSearch=p.querySelector("#room-reservation-search")?.value||"";render()});  p.querySelector("#room-reservation-search-field")?.addEventListener("change",e=>{state.roomReservationSearchField=e.target.value||"all";render()});  p.querySelector("#room-reservation-date-from")?.addEventListener("change",e=>{state.roomReservationDateFrom=e.target.value||"";render()});  p.querySelector("#room-reservation-date-to")?.addEventListener("change",e=>{state.roomReservationDateTo=e.target.value||"";render()});  p.querySelector("#room-status-filter")?.addEventListener("change",e=>{state.roomStatus=e.target.value;render()});  p.querySelector("#room-active-filter")?.addEventListener("change",e=>{
  state.roomActiveFilter=e.target.value;
  render();
});
 p.querySelector("#room-status-clear")?.addEventListener("click",()=>{state.roomStatus="";state.roomReservationSearchField="all";state.roomReservationDateFrom="";state.roomReservationDateTo="";state.roomReservationSearch="";render()});
 p.querySelector("[data-room-exit]")?.addEventListener("click",()=>{state.page="dashboard";state.roomSection="overview";render()});
 p.querySelectorAll("[data-room-financial]").forEach(b=>{
   const open=async()=>{
     try{
       const kind=b.dataset.roomFinancial;
       if(kind==="outstanding"){
         const rows=(await api("/room-bookings")).data||[];
         const pending=rows.filter(row=>Number(row.balance_amount||Math.max(0,Number(row.grand_total||row.total_amount||0)-Number(row.paid_amount||0)))>0.009);
         showRoomDetailsModal("Outstanding Room Payments",pending.map(row=>({
           booking_id:row.booking_id, guest:row.customer_name, mobile:row.customer_mobile,
           room:row.room_number, check_in:row.check_in_date, total:money(row.grand_total||row.total_amount||0),
           paid:money(row.paid_amount||0), outstanding:money(row.balance_amount||Math.max(0,Number(row.grand_total||row.total_amount||0)-Number(row.paid_amount||0)))
         })));
         return;
       }
       const rows=(await api("/room-payments?limit=200")).data||[];
       const filtered=kind==="today"?rows.filter(row=>{
         const raw=String(row.payment_date||row.created_at||row.transaction_date||"");
         return istDateKey(raw)===dateNow();
       }):rows;
       showRoomDetailsModal(kind==="today"?"Today's Room Payments":"Room Payment History",filtered.map(row=>({
         transaction_id:row.transaction_id||row.payment_id||"—",
         booking_id:row.booking_id||"—", amount:money(row.amount||row.paid_amount||0),
         payment_method:row.payment_method||"—", payment_date:istDateTime(row.payment_date||row.created_at||row.transaction_date||"")
       })));
     }catch(e){toast(e?.message||"Could not load room details.",true);}
   };
   b.addEventListener("click",open);
   b.addEventListener("keydown",e=>{if(e.key==="Enter"||e.key===" "){e.preventDefault();open()}});
 });
 p.querySelector("#room-avail-btn")?.addEventListener("click",()=>{state.roomAvailabilityDate=p.querySelector("#room-avail-date").value||dateNow();state.roomAvailabilityNights=Number(p.querySelector("#room-avail-nights").value||1);render()});
 p.querySelector("[data-back-rooms]")?.addEventListener("click",()=>render());
 p.querySelectorAll("[data-res-action]").forEach(b=>b.onclick=()=>reservationAction(b.dataset.resAction,b.dataset.bookingId));
 p.querySelectorAll("[data-guest-service-status]").forEach(b=>b.onclick=async()=>{try{await api(`/guest-services/requests/${encodeURIComponent(b.dataset.guestServiceStatus)}/status`,{method:"PATCH",body:JSON.stringify({status:b.dataset.nextStatus})});toast("Guest service status updated.");document.getElementById("page").innerHTML=`<div class="loading">Loading reservation…</div>`;document.getElementById("page").innerHTML=await reservationDetail(b.closest("[data-booking-id]")?.dataset.bookingId||window.__lastReservationBookingId||"");bindPageEvents()}catch(e){toast(e.message,true)}});
  p.querySelectorAll("[data-guest-service-pay]").forEach(btn=>btn.onclick=()=>openReceivePaymentModal(btn.dataset.bookingId,btn.dataset.guestServicePay));
 p.querySelectorAll("[data-page]").forEach(b=>b.onclick=()=>{state.page=b.dataset.page;render()});
 p.querySelectorAll("[data-open-booking]").forEach(b=>b.onclick=async()=>{
  try{
    state.page="frontdesk";

    document.getElementById("page").innerHTML=
      `<div class="loading">Loading reservation…</div>`;

    document.getElementById("page").innerHTML=
      await reservationDetail(b.dataset.openBooking);

    bindPageEvents();

  }catch(e){
    document.getElementById("page").innerHTML=
      `<div class="error-box">
        <h3>Could not load reservation</h3>
        <p>${esc(e?.message||"Unknown error")}</p>
        <button data-back-rooms>Back to Rooms & Reservations</button>
      </div>`;

    document.querySelector("[data-back-rooms]")?.addEventListener(
      "click",
      ()=>render()
    );
  }
});
 p.querySelectorAll("[data-front-action]").forEach(b=>b.onclick=async()=>{if(!isActionAllowed("room_status")){showAccessDenied();return;}try{const action=b.dataset.frontAction,id=encodeURIComponent(b.dataset.bookingId||"");if(!id){toast("Reservation not found.",true);return;}const endpoint=action==="check-in"?`/room-bookings/${id}/check-in`:`/room-bookings/${id}/check-out`;await api(endpoint,{method:"POST",body:"{}"});toast(action==="check-in"?"Guest checked in.":"Guest checked out.");render()}catch(e){toast(e.message,true)}});
 p.querySelector("#frontdesk-lookup-btn")?.addEventListener("click",async()=>{const q=p.querySelector("#frontdesk-lookup")?.value.trim();const target=p.querySelector("#frontdesk-lookup-results");if(!q){target.innerHTML=`<div class="empty-state">Enter a guest name, mobile or customer ID.</div>`;return;}try{target.innerHTML=`<div class="loading">Searching…</div>`;const r=await api(`/frontdesk/guest-lookup?q=${encodeURIComponent(q)}`);target.innerHTML=(r.data||[]).length?table(r.data||[],row=>`<button data-open-booking="${esc(row.booking_id||"")}">View</button>`):`<div class="empty-state">No matching guest records found.</div>`;target.querySelectorAll("[data-open-booking]").forEach(b=>b.onclick=async()=>{document.getElementById("page").innerHTML=`<div class="loading">Loading reservation…</div>`;document.getElementById("page").innerHTML=await reservationDetail(b.dataset.openBooking);bindPageEvents()})}catch(e){target.innerHTML=`<div class="error-box">${esc(e.message)}</div>`}});
 p.querySelector("#frontdesk-res-search-btn")?.addEventListener("click",async()=>{const q=p.querySelector("#frontdesk-res-search")?.value.trim();const target=p.querySelector("#frontdesk-res-results");if(!q){target.innerHTML=table((d.reservation_results||[]),rowActions);return;}try{const r=await api(`/frontdesk?search=${encodeURIComponent(q)}`);const data=r.data||{};target.innerHTML=(data.reservation_results||[]).length?table(data.reservation_results||[],rowActions):`<div class="empty-state">No matching reservations found.</div>`;bindPageEvents()}catch(e){target.innerHTML=`<div class="error-box">${esc(e.message)}</div>`}});
 p.querySelector("#frontdesk-res-clear")?.addEventListener("click",()=>render());
}
function openReservationEdit(b){

    if(!isActionAllowed("room_status")){
        showAccessDenied();
        return;
    }

    const status=String(b?.booking_status||"");
    if(!["Pending","Confirmed"].includes(status)){
        toast("Only Pending or Confirmed reservations can be modified.",true);
        return;
    }

    return formModal("Modify Reservation",[
        {
            name:"customer_name",
            label:"Guest name",
            required:false,
            value:b.customer_name||""
        },
        {
            name:"customer_mobile",
            label:"Mobile",
            required:false,
            value:b.customer_mobile||""
        },
        {
            name:"room_number",
            label:"Room number(s)",
            required:false,
            value:b.room_number||""
        },
        {
            name:"check_in_date",
            label:"Check-in date",
            type:"date",
            required:false,
            value:toInputDate(b.check_in_date)
        },
        {
            name:"nights",
            label:"Nights",
            type:"number",
            required:false,
            value:b.nights||b.days||1
        },
        {
            name:"adults",
            label:"Adults",
            type:"number",
            required:false,
            value:b.adults||1
        },
        {
            name:"children",
            label:"Children",
            type:"number",
            required:false,
            value:b.children||0
        },
        {
            name:"notes",
            label:"Special requests",
            required:false,
            value:b.notes||"",
            full:true
        }
    ],o=>{


    return api(
        `/room-bookings/${encodeURIComponent(b.booking_id)}`,
        {
            method:"PATCH",
            body:JSON.stringify(o)
        }
    );
});
}
function toInputDate(v){if(!v)return "";const m=String(v).match(/^(\d{2})-(\d{2})-(\d{4})$/);return m?`${m[3]}-${m[2]}-${m[1]}`:String(v).slice(0,10)}
async function openReceivePaymentModal(bookingId,extraChargeId=null){
  if(!isActionAllowed("room_payment_create")){showAccessDenied();return;}
  try{
    const r=await api(`/room-payments/${encodeURIComponent(bookingId)}/folio`);
    const b=r.data?.booking||{};
    const folio=r.data?.folio||{};
    const extraCharges=Array.isArray(r.data?.extra_charges)?r.data.extra_charges:[];
    const targetExtra=extraChargeId ? extraCharges.find(x=>String(x.charge_id)===String(extraChargeId)) : null;
    const reservationBillServices=extraCharges.filter(x=>String(x.billing_mode||"")==="Reservation Bill" && Number(x.balance_amount||0)>0.01);
    const totalBalance=Math.max(0,Number(folio.balance_amount ?? b.balance_amount ?? 0));
    const initialBalance=Math.max(0,Number(targetExtra?.balance_amount ?? totalBalance));
    if(initialBalance<=0.01){
      toast(targetExtra?"This guest service is already fully paid.":"This reservation is already fully settled.",true);
      return;
    }

    const allocationOptions=!extraChargeId ? `
      <label class="full">
        Apply payment to
        <select name="payment_target" data-payment-target>
          <option value="auto">Reservation balance — room/GST first, then services</option>
          ${reservationBillServices.map(x=>`<option value="service:${esc(x.charge_id)}">${esc(x.description||"Guest Service")} — ${money(x.balance_amount||0)} due</option>`).join("")}
        </select>
        <span class="section-note">Choose a specific service when the guest is paying for that service. Otherwise the payment is allocated to the room balance first.</span>
      </label>` : "";

    const modal=document.createElement("div");
    modal.className="modal-backdrop";
    modal.innerHTML=`
      <div class="modal reservation-receive-payment-modal">
        <div class="page-head">
          <div>
            <h2>${extraChargeId?"Receive Guest Service Payment":"Receive Reservation Payment"}</h2>
            <span class="section-note">${extraChargeId?esc(targetExtra?.description||"Guest Service"):"Record a reservation payment and choose exactly where it should be applied."}</span>
          </div>
          <button type="button" data-close>✕</button>
        </div>

        <div class="reservation-payment-due">
          <span>Outstanding balance</span>
          <strong data-payment-due>${money(initialBalance)}</strong>
        </div>

        <form class="form-grid" data-receive-payment-form>
          ${allocationOptions}
          <label>
            Payment amount
            <input
              name="amount"
              type="number"
              min="0.01"
              max="${esc(initialBalance.toFixed(2))}"
              step="0.01"
              value="${esc(initialBalance.toFixed(2))}"
              required
            >
          </label>
          <label>
            Payment method
            <select name="payment_method" required>
              <option value="">Select payment method</option>
              <option value="Cash">Cash</option>
              <option value="UPI">UPI</option>
              <option value="Card">Card</option>
              <option value="Bank Transfer">Bank Transfer</option>
              <option value="Other">Other</option>
            </select>
          </label>
          <label class="full">
            Payment note
            <input name="notes" type="text" placeholder="Optional note">
          </label>

          <div class="full form-actions">
            <button type="button" data-close>Cancel</button>
            <button class="primary" type="submit">Record Payment</button>
          </div>
          <p class="form-error full" data-error></p>
        </form>
      </div>`;

    document.body.appendChild(modal);
    modal.querySelectorAll("[data-close]").forEach(x=>x.onclick=()=>modal.remove());

    const form=modal.querySelector("form");
    const amountInput=form.querySelector('[name="amount"]');
    const targetSelect=form.querySelector('[name="payment_target"]');
    const dueEl=modal.querySelector("[data-payment-due]");
    const updatePaymentTarget=()=>{
      let selectedBalance=initialBalance;
      if(targetSelect){
        const value=String(targetSelect.value||"auto");
        if(value.startsWith("service:")){
          const id=value.slice(8);
          const target=reservationBillServices.find(x=>String(x.charge_id)===id);
          selectedBalance=Math.max(0,Number(target?.balance_amount||0));
        }
      }
      dueEl.textContent=money(selectedBalance);
      amountInput.max=selectedBalance.toFixed(2);
      amountInput.value=selectedBalance.toFixed(2);
      amountInput.dataset.targetBalance=selectedBalance.toFixed(2);
    };
    targetSelect?.addEventListener("change",updatePaymentTarget);

    form.onsubmit=async e=>{
      e.preventDefault();
      const fd=new FormData(e.target);
      const amount=Number(fd.get("amount"));
      const paymentMethod=String(fd.get("payment_method")||"").trim();
      const notes=String(fd.get("notes")||"").trim();
      const targetValue=String(fd.get("payment_target")||"auto");
      const selectedBalance=Number(amountInput.dataset.targetBalance||initialBalance);

      if(!Number.isFinite(amount)||amount<=0){
        modal.querySelector("[data-error]").textContent="Enter a valid payment amount.";
        return;
      }
      if(amount>selectedBalance+0.01){
        modal.querySelector("[data-error]").textContent=`Payment cannot exceed the selected outstanding balance of ${money(selectedBalance)}.`;
        return;
      }
      if(!paymentMethod){
        modal.querySelector("[data-error]").textContent="Select a payment method.";
        return;
      }

      const submit=e.target.querySelector('button[type="submit"]');
      submit.disabled=true;
      modal.querySelector("[data-error]").textContent="";

      try{
        const payload={
          amount:Number(amount.toFixed(2)),
          payment_method:paymentMethod,
          notes:notes||undefined
        };
        if(targetValue.startsWith("service:")) payload.extra_charge_id=targetValue.slice(8);
        await api(`/room-payments/${encodeURIComponent(bookingId)}`,{
          method:"POST",
          body:JSON.stringify(payload)
        });
        modal.remove();
        toast(targetValue.startsWith("service:")?"Guest service payment recorded successfully.":"Reservation payment recorded successfully.");
        await render();
      }catch(err){
        modal.querySelector("[data-error]").textContent=err?.message||"Could not record payment.";
        submit.disabled=false;
      }
    };
  }catch(e){
    toast(e.message||"Could not open payment form.",true);
  }
}

async function openPaymentHistoryModal(bookingId){
  try{
    const r=await api(`/room-payments/${encodeURIComponent(bookingId)}/folio`);
    const b=r.data?.booking||{};
    const folio=r.data?.folio||{};
    const transactionsRaw=Array.isArray(r.data?.transactions)?r.data.transactions:[];
    const transactions=transactionsRaw.map(row=>({...row,created_at:istDateTime(row.created_at)}));
    const extrasRaw=Array.isArray(r.data?.extra_charges)?r.data.extra_charges:[];
    const extras=extrasRaw.map(row=>({...row,created_at:istDateTime(row.created_at),updated_at:istDateTime(row.updated_at)}));
    const total=Number(folio.grand_total ?? b.grand_total ?? 0);
    const paid=Number(folio.paid_amount ?? b.paid_amount ?? 0);
    const balance=Number(folio.balance_amount ?? b.balance_amount ?? 0);
    const modal=document.createElement("div");
    modal.className="modal-backdrop";
    modal.innerHTML=`
      <div class="modal" style="max-width:900px">
        <div class="page-head">
          <div>
            <h2>Payment History — ${esc(b.customer_name||"Guest")}</h2>
            <span class="section-note">Completed reservation payment records</span>
          </div>
          <button data-close>✕</button>
        </div>
        <div class="grid cards">
          ${metric("Grand Total",money(total),"Room + reservation-bill services")}
          ${metric("Paid",money(paid),"Recorded payments")}
          ${metric("Outstanding",money(balance),"Current balance")}
          ${metric("Booking Status",b.booking_status||"—","Current status")}
        </div>
        <div class="card" style="margin-top:15px">
          <h3>Payment History</h3>
          ${table(transactions)}
        </div>
        ${extras.length?`<div class="card" style="margin-top:15px"><h3>Extra Charges</h3>${table(extras)}</div>`:""}
        <div class="form-actions" style="margin-top:15px">
          <button type="button" data-close>Close</button>
        </div>
      </div>`;
    document.body.appendChild(modal);
    modal.querySelectorAll("[data-close]").forEach(x=>x.onclick=()=>modal.remove());
  }catch(e){
    toast(e.message||"Could not load payment history.",true);
  }
}

async function openCheckoutModal(bookingId){
  try{
    const r=await api(`/room-payments/${encodeURIComponent(bookingId)}/folio`);
    const b=r.data?.booking||{};
    const folio=r.data?.folio||{};
    const transactionsRaw=Array.isArray(r.data?.transactions)?r.data.transactions:[];
    const transactions=transactionsRaw.map(row=>({...row,created_at:istDateTime(row.created_at)}));
    const extrasRaw=Array.isArray(r.data?.extra_charges)?r.data.extra_charges:[];
    const extras=extrasRaw.map(row=>({...row,created_at:istDateTime(row.created_at),updated_at:istDateTime(row.updated_at)}));
    const roomTotal=Number(folio.room_total ?? b.grand_total ?? 0);
    const serviceTotal=Number(folio.service_total ?? 0);
    const paid=Number(folio.paid_amount ?? b.paid_amount ?? 0);
    const roomPaid=Number(folio.room_paid ?? b.paid_amount ?? 0);
    const servicePaid=Number(folio.service_paid ?? 0);
    const roomBalance=Number(folio.room_balance ?? b.balance_amount ?? 0);
    const serviceBalance=Number(folio.service_balance ?? 0);
    const reservationGrandTotal=Number(folio.grand_total ?? (roomTotal+serviceTotal));
    const totalOutstanding=Number(folio.balance_amount ?? (roomBalance+serviceBalance));
    const bookedNights=Math.max(1,Number(b.nights||b.days||1));
    const expected=String(b.expected_check_out||"");
    const expectedParts=expected.match(/^(\d{2})-(\d{2})-(\d{4})$/);
    const expectedDate=expectedParts
      ? new Date(Number(expectedParts[3]),Number(expectedParts[2])-1,Number(expectedParts[1]))
      : null;
    const today=new Date();
    today.setHours(0,0,0,0);
    const isEarly=expectedDate ? today < expectedDate : false;
    const checkoutType=isEarly?"Early":"Standard";

    const modal=document.createElement("div");
    modal.className="modal-backdrop";
    modal.innerHTML=`
      <div class="modal" style="max-width:980px">
        <div class="page-head">
          <div>
            <h2>${isEarly?"Early Check-out":"Check-out Guest"}</h2>
            <span class="section-note">${isEarly?"Expected check-out is "+esc(expected)+". Select the hotel's settlement policy.":"Final stay settlement and room release."}</span>
          </div>
          <button data-close>✕</button>
        </div>

        <div class="grid cards">
          ${metric("Guest Name",b.customer_name||"—","Guest")}
          ${metric("Room No.",b.room_number||"—",b.room_type||"Room")}
          ${metric("Booked Nights",bookedNights,"Reservation")}
          ${metric("Collect Payment",money(paid),"Received payment")}
          ${metric("Room",money(roomTotal),"Room + GST")}
          ${metric("Other Service Charge",money(serviceTotal),"Reservation-bill services")}
          ${metric("Grand Total",money(reservationGrandTotal),"Room + services")}
          ${metric("Outstanding",money(totalOutstanding),totalOutstanding<=0.01?"Ready":"Payment pending")}
        </div>

        ${isEarly?`
        <div class="card" style="margin-top:15px">
          <h3>Early Check-out Settlement</h3>
          <p class="section-note">The hotel decides how the early departure is settled. The selected rule is recorded with the reservation.</p>
          <div class="form-grid">
            <label>
              Policy
              <select data-early-policy>
                <option value="STAYED_NIGHTS">Charge actual stayed nights</option>
                <option value="FULL_BOOKING">Charge full booked stay</option>
                <option value="STAYED_NIGHTS_PLUS_FEE">Stayed nights + extra fee</option>
                <option value="CUSTOM">Custom final amount</option>
                <option value="WAIVE">Waive remaining amount / no additional payment</option>
              </select>
            </label>
            <label data-fee-wrap style="display:none">
              Early check-out fee
              <input data-early-fee type="number" min="0" step="0.01" value="0">
            </label>
            <label data-custom-wrap style="display:none">
              Custom final amount
              <input data-custom-final type="number" min="0" step="0.01" value="${roomTotal.toFixed(2)}">
            </label>
            <label class="full">
              Settlement note
              <textarea data-checkout-notes rows="2" placeholder="Optional reason or policy note"></textarea>
            </label>
          </div>
          <div class="grid cards" style="margin-top:12px">
            <div class="card metric"><div class="label">Final Room Charge</div><div class="value" data-final-room-charge>${money(roomTotal)}</div><div class="sub">After stay settlement</div></div>
            <div class="card metric"><div class="label">Other Service Charge</div><div class="value" data-service-total>${money(serviceTotal)}</div><div class="sub">Kept separate</div></div>
            <div class="card metric"><div class="label">Final Grand Total</div><div class="value" data-final-grand-total>${money(reservationGrandTotal)}</div><div class="sub">Room + services</div></div>
            <div class="card metric"><div class="label">Payment / Refund</div><div class="value" data-settlement-difference>—</div><div class="sub">Compared with received payment</div></div>
          </div>
        </div>`:""}

        ${isEarly?`
        <div class="card" style="margin-top:15px">
          <h3 data-checkout-settlement-title>Checkout Payment</h3>
          <p class="section-note" data-checkout-settlement-note>If an amount is still due, record the actual payment before confirming check-out.</p>
          <div class="form-grid">
            <label>
              <span data-checkout-settlement-amount-label>Amount to Collect</span>
              <input data-checkout-payment-amount type="number" min="0" step="0.01" value="0" readonly>
            </label>
            <label>
              <span data-checkout-settlement-method-label>Payment Method</span>
              <select data-checkout-payment-method>
                <option value="Cash">Cash</option>
                <option value="UPI">UPI</option>
                <option value="Card">Card</option>
                <option value="Other">Other</option>
              </select>
            </label>
            <label class="full">
              <span data-checkout-settlement-note-label>Payment Note</span>
              <input data-checkout-payment-note type="text" placeholder="Optional payment note">
            </label>
          </div>
          <div class="form-actions" style="margin-top:12px">
            <button type="button" class="primary" data-record-checkout-payment>Record Payment</button>
          </div>
          <p class="form-error" data-payment-error></p>
        </div>`:""}

        <div class="card" style="margin-top:15px">
          <h3>Payment History</h3>
          ${table(transactions)}
        </div>
        ${extras.length?`<div class="card" style="margin-top:15px"><h3>Extra Charges</h3>${table(extras)}</div>`:""}

        <div class="form-actions" style="margin-top:15px">
          <button type="button" data-close>Cancel</button>
          <button class="primary" data-confirm-checkout>Confirm ${isEarly?"Early ":""}Check-out</button>
        </div>
        <p class="form-error" data-error></p>
      </div>`;

    document.body.appendChild(modal);

    const policyEl=modal.querySelector("[data-early-policy]");
    const feeWrap=modal.querySelector("[data-fee-wrap]");
    const customWrap=modal.querySelector("[data-custom-wrap]");
    const feeEl=modal.querySelector("[data-early-fee]");
    const customEl=modal.querySelector("[data-custom-final]");
    const finalEl=modal.querySelector("[data-final-room-charge]");
    const diffEl=modal.querySelector("[data-settlement-difference]");
    const errorEl=modal.querySelector("[data-error]");
    const confirm=modal.querySelector("[data-confirm-checkout]");
    const paymentAmountEl=modal.querySelector("[data-checkout-payment-amount]");
    const paymentMethodEl=modal.querySelector("[data-checkout-payment-method]");
    const paymentNoteEl=modal.querySelector("[data-checkout-payment-note]");
    const recordPaymentBtn=modal.querySelector("[data-record-checkout-payment]");
    const paymentErrorEl=modal.querySelector("[data-payment-error]");

    function updateEarlyPreview(){
      if(!isEarly)return;
      const policy=policyEl.value;
      feeWrap.style.display=policy==="STAYED_NIGHTS_PLUS_FEE"?"":"none";
      customWrap.style.display=policy==="CUSTOM"?"":"none";

      const getActualStayNights=()=>{
        const raw=String(b.actual_check_in||"").trim();
        if(!raw)return 1;
        const match=raw.match(/^(\d{4})-(\d{2})-(\d{2})/);
        if(!match)return 1;
        const checkInDay=new Date(Number(match[1]),Number(match[2])-1,Number(match[3]));
        checkInDay.setHours(0,0,0,0);
        return Math.max(1,Math.min(bookedNights,Math.floor((today-checkInDay)/(24*60*60*1000))+1));
      };
      const actualStayNights=getActualStayNights();
      let finalRoomCharge=roomTotal;
      if(policy==="STAYED_NIGHTS"){
        finalRoomCharge=roomTotal*actualStayNights/bookedNights;
      }else if(policy==="STAYED_NIGHTS_PLUS_FEE"){
        finalRoomCharge=roomTotal*actualStayNights/bookedNights+Number(feeEl.value||0);
      }else if(policy==="CUSTOM"){
        finalRoomCharge=Number(customEl.value||0);
      }else if(policy==="WAIVE"){
        finalRoomCharge=roomPaid;
      }

      finalRoomCharge=Math.max(0,Number(finalRoomCharge||0));
      const finalGrandTotal=finalRoomCharge+serviceTotal;
      const difference=finalGrandTotal-paid;
      finalEl.textContent=money(finalRoomCharge);
      modal.querySelector("[data-service-total]").textContent=money(serviceTotal);
      modal.querySelector("[data-final-grand-total]").textContent=money(finalGrandTotal);

      if(difference>0.01){
        diffEl.textContent=`Collect ${money(difference)}`;
      }else if(difference<-0.01){
        diffEl.textContent=`Refund ${money(Math.abs(difference))}`;
      }else{
        diffEl.textContent="Settled";
      }
      if(paymentAmountEl){
        const needsRefund=difference < -0.01;
        const needsCollect=difference > 0.01;
        const amount=Math.abs(difference);
        const titleEl=modal.querySelector("[data-checkout-settlement-title]");
        const noteEl=modal.querySelector("[data-checkout-settlement-note]");
        const amountLabelEl=modal.querySelector("[data-checkout-settlement-amount-label]");
        const methodLabelEl=modal.querySelector("[data-checkout-settlement-method-label]");
        const noteLabelEl=modal.querySelector("[data-checkout-settlement-note-label]");
        if(needsRefund){
          titleEl.textContent="Refund Payment";
          noteEl.textContent="Refund the calculated amount to the guest before confirming check-out.";
          amountLabelEl.textContent="Refund Amount";
          methodLabelEl.textContent="Refund Method";
          noteLabelEl.textContent="Refund Note";
          paymentNoteEl.placeholder="Optional refund note";
          recordPaymentBtn.textContent="Record Refund";
        }else{
          titleEl.textContent="Checkout Payment";
          noteEl.textContent="If an amount is still due, record the actual payment before confirming check-out.";
          amountLabelEl.textContent="Amount to Collect";
          methodLabelEl.textContent="Payment Method";
          noteLabelEl.textContent="Payment Note";
          paymentNoteEl.placeholder="Optional payment note";
          recordPaymentBtn.textContent="Record Payment";
        }
        paymentAmountEl.value=(needsRefund||needsCollect)?amount.toFixed(2):"0.00";
        paymentAmountEl.max=(needsRefund||needsCollect)?amount.toFixed(2):"0";
        paymentAmountEl.readOnly=true;
        recordPaymentBtn.disabled=!(needsRefund||needsCollect);
      }
    }

    modal.querySelectorAll("[data-close]").forEach(x=>x.onclick=()=>modal.remove());
    if(policyEl){
      policyEl.onchange=updateEarlyPreview;
      feeEl.oninput=updateEarlyPreview;
      customEl.oninput=updateEarlyPreview;
      updateEarlyPreview();
    }

    if(recordPaymentBtn){
      recordPaymentBtn.onclick=async()=>{
        paymentErrorEl.textContent="";
        const amount=Number(paymentAmountEl.value||0);
        const allowed=Number(paymentAmountEl.max||0);
        const isRefund=String(recordPaymentBtn.textContent||"").toLowerCase().includes("refund");
        if(!(amount>0))return paymentErrorEl.textContent="The settlement amount must be greater than ₹0.";
        if(allowed>0 && Math.abs(amount-allowed)>0.01){
          return paymentErrorEl.textContent=`Settlement amount must equal ${money(allowed)}.`;
        }
        recordPaymentBtn.disabled=true;
        try{
          const result=isRefund
            ? await api(`/room-payments/${encodeURIComponent(bookingId)}/refund`,{
                method:"POST",
                body:JSON.stringify({
                  amount,
                  payment_method:paymentMethodEl.value,
                  checkout_policy:policyEl.value,
                  extra_fee:Number(feeEl?.value||0),
                  custom_final_amount:policyEl.value==="CUSTOM"?Number(customEl.value||0):null,
                  notes:paymentNoteEl.value.trim()||"Early check-out refund"
                })
              })
            : await api(`/room-payments/${encodeURIComponent(bookingId)}`,{
                method:"POST",
                body:JSON.stringify({
                  amount,
                  payment_method:paymentMethodEl.value,
                  notes:paymentNoteEl.value.trim()||"Checkout payment"
                })
              });
          modal.remove();
          toast(result?.message||(isRefund?"Refund recorded successfully.":"Room payment recorded successfully."));
          await render();
          await openCheckoutModal(bookingId);
        }catch(err){
          recordPaymentBtn.disabled=false;
          paymentErrorEl.textContent=err.message||"Settlement could not be recorded.";
        }
      };
    }

    confirm.onclick=async()=>{
      confirm.disabled=true;
      errorEl.textContent="";
      try{
        let payload={
          checkout_type:checkoutType,
          checkout_policy:isEarly?policyEl.value:"FULL_BOOKING",
          extra_fee:isEarly?Number(feeEl?.value||0):0,
          custom_final_amount:isEarly&&policyEl.value==="CUSTOM"?Number(customEl.value||0):null,
          notes:modal.querySelector("[data-checkout-notes]")?.value?.trim()||null
        };
        const result=await api(`/room-bookings/${encodeURIComponent(bookingId)}/check-out`,{
          method:"POST",
          body:JSON.stringify(payload)
        });
        modal.remove();
        const msg=result?.message || (isEarly?"Early check-out completed.":"Guest checked out successfully.");
        toast(msg);
        render();
      }catch(err){
        confirm.disabled=false;
        errorEl.textContent=err.message||"Check-out failed.";
      }
    };
  }catch(e){
    toast(e.message||"Could not load checkout details.",true);
  }
}

async function openBookedRoomActionMenu(bookingId){
  try{
    if(!bookingId) throw new Error("Reservation record was not found.");
    const r=await api(`/room-bookings?booking_id=${encodeURIComponent(bookingId)}`);
    const b=r.data||{};
    const status=String(b.booking_status||"");
    if(!["Pending","Confirmed"].includes(status)){
      toast("This reservation is no longer in Booked Rooms.",true);
      await render();
      return;
    }

    const checkInRaw=String(b.check_in_date||"").trim().slice(0,10);
    // API payloads may contain ISO dates (YYYY-MM-DD) or display dates (DD-MM-YYYY).
    // Parse explicitly in local calendar time to avoid browser-dependent date parsing.
    let checkInDate=null;
    let dateMatch=checkInRaw.match(/^(\d{4})-(\d{2})-(\d{2})$/);
    if(dateMatch){
      checkInDate=new Date(Number(dateMatch[1]),Number(dateMatch[2])-1,Number(dateMatch[3]));
    }else{
      dateMatch=checkInRaw.match(/^(\d{2})-(\d{2})-(\d{4})$/);
      if(dateMatch) checkInDate=new Date(Number(dateMatch[3]),Number(dateMatch[2])-1,Number(dateMatch[1]));
    }
    const today=new Date();
    today.setHours(0,0,0,0);
    const isPastDue=Boolean(checkInDate && !Number.isNaN(checkInDate.getTime()) && checkInDate<today);
    const modal=document.createElement("div");
    modal.className="modal-backdrop";
    modal.innerHTML=`<div class="modal" style="max-width:560px">
      <div class="page-head"><div><h2>Booked Room Actions</h2><span class="section-note">${esc(b.customer_name||"Guest")} · Room ${esc(b.room_number||"—")}</span></div><button type="button" data-close>✕</button></div>
      <div class="grid two" style="margin-top:15px">
        ${isActionAllowed("room_status") ? `<button type="button" class="primary" data-booked-action="check-in">Check-in</button>` : ""}
        ${!isPastDue && isActionAllowed("room_status") ? `<button type="button" data-booked-action="early-check-in">Early Check-in</button>` : ""}
        ${isPastDue ? `<button type="button" data-booked-action="contact-guest">Contact Guest</button><button type="button" data-booked-action="keep-pending">Keep Pending</button>` : ""}
        ${isPastDue && isActionAllowed("room_status") ? `<button type="button" data-booked-action="no-show">Mark as No-Show</button>` : ""}
        ${isActionAllowed("room_cancel") ? `<button type="button" data-booked-action="cancel">Cancel Reservation</button>` : ""}
      </div>
      <p class="section-note" style="margin-top:14px">${isPastDue ? "This reservation is past its check-in date. Contact the guest and confirm their status before marking No-Show. Keeping it pending will not cancel the booking." : "Check-in moves the reservation to Occupied. Early Check-in is available only before the scheduled check-in date. Cancellation opens the cancellation and refund form."}</p>
    </div>`;
    document.body.appendChild(modal);
    const close=()=>modal.remove();
    modal.querySelectorAll("[data-close]").forEach(x=>x.onclick=close);
    modal.querySelectorAll("[data-booked-action]").forEach(btn=>btn.onclick=async()=>{
      const action=btn.dataset.bookedAction;
      close();
      try{
        if(action==="cancel") return openCancellationModal(bookingId);
        if(action==="check-in") return reservationAction("check-in",bookingId);
        if(action==="keep-pending"){
          toast("Reservation remains pending. No status or payment was changed.");
          return;
        }
        if(action==="contact-guest"){
          const phone=String(b.customer_mobile||"").trim();
          const contact=document.createElement("div");
          contact.className="modal-backdrop";
          contact.innerHTML=`<div class="modal" style="max-width:440px"><div class="page-head"><div><h2>Contact Guest</h2><span class="section-note">${esc(b.customer_name||"Guest")} · Room ${esc(b.room_number||"—")}</span></div><button type="button" data-close>✕</button></div><p style="margin:18px 0 8px">Mobile number</p><strong>${esc(phone||"No mobile number saved")}</strong><p class="section-note" style="margin-top:12px">Contact the guest to confirm arrival. The reservation will remain Pending until you take another action.</p><div class="room-row-actions" style="margin-top:18px">${phone?`<a class="button primary" href="tel:${esc(phone)}">Call Guest</a>`:""}<button type="button" data-close>Done</button></div></div>`;
          document.body.appendChild(contact);
          contact.querySelectorAll("[data-close]").forEach(x=>x.onclick=()=>contact.remove());
          return;
        }
        if(action==="no-show") return openNoShowSettlementModal(bookingId);
        if(action==="early-check-in"){
          const now=new Date();
          const pad=n=>String(n).padStart(2,"0");
          const earlyTime=`${now.getFullYear()}-${pad(now.getMonth()+1)}-${pad(now.getDate())} ${pad(now.getHours())}:${pad(now.getMinutes())}`;
          await api(`/room-bookings/${encodeURIComponent(bookingId)}/stay-options`,{
            method:"PATCH",
            body:JSON.stringify({early_check_in_time:earlyTime,late_check_out_time:null})
          });
          return reservationAction("check-in",bookingId);
        }
      }catch(e){toast(e.message||"Booked room action failed.",true);}
    });
  }catch(e){toast(e.message||"Could not load booked room actions.",true);}
}

async function openNoShowSettlementModal(bookingId){
  try{
    const [bookingResult, folioResult, serviceRequestsResult, serviceCatalogResult] = await Promise.all([
      api(`/room-bookings?booking_id=${encodeURIComponent(bookingId)}`),
      api(`/room-payments/${encodeURIComponent(bookingId)}/folio`),
      api(`/guest-services/requests?booking_id=${encodeURIComponent(bookingId)}`),
      api(`/guest-services/catalog`)
    ]);
    const b=bookingResult.data||{};
    const folioResponse=folioResult.data||{};
    const folio=folioResponse.folio||folioResponse||{};
    const extraCharges=Array.isArray(folioResponse.extra_charges)?folioResponse.extra_charges:[];
    const paid=Math.max(0,Number(folio.gross_paid_amount ?? folio.paid_amount ?? b.paid_amount ?? 0));
    const alreadyRefunded=Math.max(0,Number(folio.refund_amount ?? b.no_show_refund_amount ?? 0));
    const refundable=Math.max(0,paid-alreadyRefunded);
    const bookingTotal=Math.max(0,Number(folio.grand_total ?? b.grand_total ?? 0));
    const outstanding=Math.max(0,Number(folio.balance_amount ?? b.balance_amount ?? 0));
    const reservationServices=extraCharges.filter(x=>String(x.billing_mode||"") === "Reservation Bill");
    const separateServices=extraCharges.filter(x=>String(x.billing_mode||"") === "Separate Payment");
    const serviceRequests=Array.isArray(serviceRequestsResult.data)?serviceRequestsResult.data:[];
    const serviceCatalog=Array.isArray(serviceCatalogResult.data)?serviceCatalogResult.data:[];
    const policyForCharge=x=>{
      const req=serviceRequests.find(r=>String(r.extra_charge_id||"")===String(x.charge_id||""));
      const cat=serviceCatalog.find(c=>Number(c.service_id)===Number(req?.service_id));
      const policy=cat?.no_show_policy||"No Charge";
      const amount=Math.max(0,Number(x.amount||0));
      const status=String(req?.request_status||"").toLowerCase();
      const feeType=cat?.cancellation_fee_type||"Fixed";
      const feeValue=Math.max(0,Number(cat?.cancellation_fee_value||0));
      let fee=policy==="Full Charge"?amount:policy==="Charge If Completed"&&["completed","complete","served"].includes(status)?amount:policy==="Cancellation Fee"?Math.min(amount,feeType==="Percent"?amount*Math.min(feeValue,100)/100:feeValue):0;
      return {req,cat,policy,fee,refundPolicy:cat?.refund_policy||"Refund Paid Amount",approval:!!Number(cat?.manager_approval_required)};
    };
    const reservationPolicyRows=reservationServices.map(x=>({x,...policyForCharge(x)}));
    const separatePolicyRows=separateServices.map(x=>({x,...policyForCharge(x)}));
    const policyFee= Math.round(reservationPolicyRows.reduce((sum,r)=>sum+r.fee,0)*100)/100;
    const policyRefundable=Math.max(0,Number(folio.room_paid ?? b.paid_amount ?? 0)+reservationPolicyRows.filter(r=>r.refundPolicy==="Refund Paid Amount").reduce((sum,r)=>sum+Math.max(0,Number(r.x.paid_amount||0)),0));
    const approvalRequired=reservationPolicyRows.some(r=>r.approval||r.refundPolicy==="Manager Approval");
    const canManagePolicy=hasPermission("Settings","Update");
    const serviceRows=charges=>charges.length?charges.map(x=>{const p=policyForCharge(x);return `<tr><td>${esc(String(x.description||"Guest Service").replace(/^Guest Service:\s*/i,""))}</td><td>${esc(x.billing_mode||"—")}</td><td>${money(x.amount||0)}</td><td>${money(x.paid_amount||0)}</td><td>${money(x.balance_amount||0)}</td><td>${esc(p.policy)}</td><td>${money(p.fee)}</td><td>${esc(p.refundPolicy)}${p.approval?" · Approval required":""}</td></tr>`}).join(""):`<tr><td colspan="8" class="section-note">No service charges recorded.</td></tr>`;
    const canRefund=isActionAllowed("room_refund");
    const modal=document.createElement("div");
    modal.className="modal-backdrop";
    modal.innerHTML=`<div class="modal" style="max-width:820px">
      <div class="page-head"><div><h2>No-Show Settlement</h2><span class="section-note">${esc(b.customer_name||"Guest")} · Room ${esc(b.room_number||"—")} · Booking ${esc(bookingId)}</span></div><button type="button" data-close>✕</button></div>
      <div class="grid cards">
        ${metric("Booking Total",money(bookingTotal),"Room + Reservation Bill services")}
        ${metric("Paid",money(paid),"Recorded payments before this settlement")}
        ${metric("Outstanding",money(outstanding),"Unpaid Reservation Bill balance")}
        ${metric("Maximum Refund",money(policyRefundable),"Limited by each service refund policy")}
      </div>
      <section class="card" style="margin-top:14px;padding:14px"><h3>Guest Services — Reservation Bill</h3><div class="table-wrap"><table><thead><tr><th>Service</th><th>Billing Mode</th><th>Charge</th><th>Paid</th><th>Outstanding</th><th>No-Show Policy</th><th>Policy Fee</th><th>Refund Policy</th></tr></thead><tbody>${serviceRows(reservationServices)}</tbody></table></div><p class="section-note">Reservation Bill service charges are included in Booking Total. Service charges are shown separately from room charges.</p></section>
      ${separateServices.length?`<section class="card" style="margin-top:10px;padding:14px"><h3>Guest Services — Separate Payment</h3><div class="table-wrap"><table><thead><tr><th>Service</th><th>Billing Mode</th><th>Charge</th><th>Paid</th><th>Outstanding</th><th>No-Show Policy</th><th>Policy Fee</th><th>Refund Policy</th></tr></thead><tbody>${serviceRows(separateServices)}</tbody></table></div><p class="section-note">These charges are tracked separately and are not included in the reservation booking total above.</p></section>`:""}
      <div class="form-grid" style="margin-top:15px">
        <label class="full">No-Show reason<textarea name="reason" rows="2" required>Guest did not arrive after contact attempt</textarea></label>
        <label>No-Show fee (₹)<input name="no_show_fee" type="number" min="0" step="0.01" value="${policyFee.toFixed(2)}"></label>
        <label>Refund amount (₹)<input name="refund_amount" type="number" min="0" max="${policyRefundable.toFixed(2)}" step="0.01" value="0" ${canRefund?"":"disabled"}></label>
        <label>Refund method<select name="refund_method" ${canRefund?"":"disabled"}><option value="">Select method if refunding</option><option>Cash</option><option>UPI</option><option>Card</option></select></label>
        <label class="full">Settlement note<input name="refund_notes" placeholder="Optional settlement / refund reference"></label>
        <label class="full"><span><input type="checkbox" name="manager_override_enabled" ${canManagePolicy?"":"disabled"} style="width:auto;margin-right:8px">Manager override — allow a different No-Show fee</span><span class="section-note">Use only when the service circumstances justify changing the configured policy fee. The reason is recorded in the settlement audit notes.</span></label>
        <label class="full" data-manager-reason-wrap ${approvalRequired?"":"hidden"}>Manager approval / override reason<textarea name="manager_override_reason" rows="2" ${canManagePolicy?"":"disabled"} placeholder="Required: explain the approval or why the configured fee is being changed"></textarea>${!canManagePolicy?`<span class="form-error">An authorized user with Settings → Update permission must complete this settlement.</span>`:""}</label>
        <p class="section-note full">Configured Guest Service policy fee: <strong>${money(policyFee)}</strong>. A lower or different fee requires an authorized manager override and a reason. The server validates the settlement before saving.</p>
      </div>
      ${!canRefund&&policyRefundable>0?`<p class="form-error">Your role does not have Billing → Refund permission. Refund must be recorded by an authorized user.</p>`:""}
      <p class="section-note">The No-Show fee is recorded for settlement reference; it is not automatically collected. Any refund is limited to the amount already received. Confirm only after verifying the guest status and hotel policy.</p>
      <p class="form-error" data-error></p>
      <div class="form-actions"><button type="button" data-close>Keep Pending</button><button type="button" class="primary" data-confirm>Confirm No-Show</button></div>
    </div>`;
    document.body.appendChild(modal);
    const close=()=>modal.remove();
    modal.querySelectorAll("[data-close]").forEach(x=>x.onclick=close);
    const amountEl=modal.querySelector('[name="refund_amount"]');
    const methodEl=modal.querySelector('[name="refund_method"]');
    const reasonEl=modal.querySelector('[name="reason"]');
    const feeEl=modal.querySelector('[name="no_show_fee"]');
    const notesEl=modal.querySelector('[name="refund_notes"]');
    const managerReasonEl=modal.querySelector('[name="manager_override_reason"]');
    const managerOverrideEl=modal.querySelector('[name="manager_override_enabled"]');
    const managerReasonWrap=modal.querySelector('[data-manager-reason-wrap]');
    const errorEl=modal.querySelector("[data-error]");
    managerOverrideEl?.addEventListener("change",()=>{if(managerReasonWrap)managerReasonWrap.hidden=!(approvalRequired||managerOverrideEl.checked);});
    modal.querySelector("[data-confirm]").onclick=async()=>{
      errorEl.textContent="";
      const reason=reasonEl.value.trim();
      const fee=Math.round(Number(feeEl.value||0)*100)/100;
      const refund=Math.round(Number(amountEl.value||0)*100)/100;
      if(!reason){errorEl.textContent="No-Show reason is required.";return;}
      const managerOverride=!!managerOverrideEl?.checked;
      const managerReason=String(managerReasonEl?.value||"").trim();
      if(!Number.isFinite(fee)||fee<0){errorEl.textContent="Enter a valid non-negative No-Show fee.";return;}
      if(fee<policyFee-0.01&&!managerOverride){errorEl.textContent=`No-Show fee must cover configured Guest Service policy fees of ${money(policyFee)} unless an authorized manager override is enabled.`;return;}
      if((approvalRequired||managerOverride)&&!managerReason){errorEl.textContent="Manager approval/override reason is required.";return;}
      if((approvalRequired||managerOverride)&&!canManagePolicy){errorEl.textContent="An authorized user with Settings → Update permission must approve this settlement.";return;}
      if(!Number.isFinite(refund)||refund<0||refund>policyRefundable+0.01){errorEl.textContent=`Refund cannot exceed ${money(policyRefundable)} under the configured Guest Service refund policies.`;return;}
      if(refund>0&&!methodEl.value){errorEl.textContent="Select a refund method.";return;}
      if(refund>0&&!canRefund){errorEl.textContent="Billing → Refund permission is required.";return;}
      if(!confirm("Confirm No-Show and save the settlement details?"))return;
      const btn=modal.querySelector("[data-confirm]");btn.disabled=true;
      try{
        const result=await api(`/room-bookings/${encodeURIComponent(bookingId)}/no-show`,{method:"POST",body:JSON.stringify({reason,no_show_fee:fee,refund_amount:refund,refund_method:methodEl.value||null,refund_notes:notesEl.value.trim()||null,manager_override_reason:managerReason||null,manager_override_enabled:managerOverride})});
        close();toast(result?.message||"No-Show settlement saved.");await render();
      }catch(e){btn.disabled=false;errorEl.textContent=e.message||"No-Show settlement failed.";}
    };
  }catch(e){toast(e.message||"Could not open No-Show settlement.",true);}
}

async function openCancellationModal(bookingId){
  try{
    if(!isActionAllowed("room_cancel")){showAccessDenied();return;}
    const r=await api(`/room-payments/${encodeURIComponent(bookingId)}/folio`);
    const b=r.data?.booking||{};
    const folio=r.data?.folio||{};
    const paid=Number(folio.gross_paid_amount ?? folio.paid_amount ?? b.paid_amount ?? 0);
    const alreadyRefunded=Number(folio.refund_amount ?? b.cancellation_refund_amount ?? 0);
    const refundable=Math.max(0,paid-alreadyRefunded);
    const canRefund=isActionAllowed("room_refund");
    const modal=document.createElement("div");
    modal.className="modal-backdrop";
    modal.innerHTML=`<div class="modal" style="max-width:760px">
      <div class="page-head"><div><h2>Cancel Reservation</h2><span class="section-note">Cancel the booking and, when applicable, record its refund in the same step.</span></div><button data-close>✕</button></div>
      <div class="grid cards">
        ${metric("Guest",b.customer_name||"—","Reservation")}
        ${metric("Room",b.room_number||"—","Assigned room")}
        ${metric("Grand Total",money(b.grand_total||folio.grand_total||0),"Reservation total")}
        ${metric("Paid",money(paid),"Recorded before refund")}
        ${metric("Refundable",money(refundable),canRefund?"Maximum available refund":"Refund permission required")}
      </div>
      <div class="form-grid" style="margin-top:15px">
        <label class="full">Cancellation reason<textarea name="reason" rows="3" required placeholder="Why is this reservation being cancelled?"></textarea></label>
        <label>Refund amount<input name="refund_amount" type="number" min="0" max="${refundable.toFixed(2)}" step="0.01" value="${refundable.toFixed(2)}" ${canRefund?"":"disabled"}></label>
        <label>Refund method<select name="refund_method" ${canRefund?"":"disabled"}><option value="">${refundable>0?"Select method":"No refund"}</option><option value="Cash">Cash</option><option value="UPI">UPI</option><option value="Card">Card</option></select></label>
        <label class="full">Refund note<input name="refund_notes" type="text" placeholder="Optional refund note" ${canRefund?"":"disabled"}></label>
      </div>
      ${!canRefund&&refundable>0?`<p class="form-error">You can cancel the reservation, but your role does not have Billing → Refund permission.</p>`:""}
      <p class="form-error" data-error></p>
      <div class="form-actions"><button type="button" data-close>Keep Reservation</button><button type="button" class="primary" data-confirm ${canRefund||refundable<=0?"":"disabled"}>Confirm Cancellation</button></div>
    </div>`;
    document.body.appendChild(modal);
    const close=()=>modal.remove();
    modal.querySelectorAll("[data-close]").forEach(x=>x.onclick=close);
    const amountEl=modal.querySelector('[name="refund_amount"]');
    const methodEl=modal.querySelector('[name="refund_method"]');
    const reasonEl=modal.querySelector('[name="reason"]');
    const notesEl=modal.querySelector('[name="refund_notes"]');
    const errorEl=modal.querySelector("[data-error]");
    modal.querySelector("[data-confirm]").onclick=async()=>{
      errorEl.textContent="";
      const reason=reasonEl.value.trim();
      const amount=Math.round(Number(amountEl.value||0)*100)/100;
      if(!reason){errorEl.textContent="Cancellation reason is required.";return;}
      if(!Number.isFinite(amount)||amount<0||amount>refundable+0.01){errorEl.textContent=`Refund cannot exceed ${money(refundable)}.`;return;}
      if(amount>0 && !methodEl.value){errorEl.textContent="Select a refund method.";return;}
      const btn=modal.querySelector("[data-confirm]"); btn.disabled=true;
      try{
        const result=await api(`/room-bookings/${encodeURIComponent(bookingId)}/cancel`,{method:"POST",body:JSON.stringify({reason,refund_amount:amount,refund_method:methodEl.value||null,refund_notes:notesEl.value.trim()||null})});
        close(); toast(result?.message||"Reservation cancelled."); render();
      }catch(e){btn.disabled=false;errorEl.textContent=e.message||"Cancellation failed.";}
    };
  }catch(e){toast(e.message||"Could not open cancellation.",true);}
}

async function reservationAction(action,bookingId){
 try{
  if(action==="modify"){
   const r=await api(`/room-bookings?booking_id=${encodeURIComponent(bookingId)}`);
   const booking=Array.isArray(r.data)
     ? r.data.find(x=>String(x.booking_id||"")===String(bookingId))
     : (r.data && String(r.data.booking_id||"")===String(bookingId) ? r.data : null);
   if(!booking)throw new Error("Reservation not found.");
   return openReservationEdit(booking);
  }
  if(action==="cancel")return openCancellationModal(bookingId);
  if(action==="no-show")return formModal("No-Show Reservation",[{name:"reason",label:"No-show reason"}],o=>api(`/room-bookings/${encodeURIComponent(bookingId)}/no-show`,{method:"POST",body:JSON.stringify(o)}));
  if(action==="transfer")return formModal("Transfer Room",[{name:"new_room_number",label:"New room number"}],o=>api(`/room-bookings/${encodeURIComponent(bookingId)}/transfer`,{method:"POST",body:JSON.stringify(o)}));
  if(action==="stay-options")return formModal("Early / Late Stay Options",[{name:"early_check_in_time",label:"Early check-in time",required:false},{name:"late_check_out_time",label:"Late check-out time",required:false}],o=>api(`/room-bookings/${encodeURIComponent(bookingId)}/stay-options`,{method:"PATCH",body:JSON.stringify(o)}));
  if(action==="payment-history") return openPaymentHistoryModal(bookingId);
  if(action==="receive-payment") return openReceivePaymentModal(bookingId);
  if(action==="check-out") return openCheckoutModal(bookingId);
  const endpoint={
  "confirm":"confirm",
  "check-in":"check-in"
}[action];
  if(endpoint){
    const result=await api(`/room-bookings/${encodeURIComponent(bookingId)}/${endpoint}`,{method:"POST",body:"{}"});
    toast(result?.message||`${endpoint} completed successfully.`);
    await render();
    return;
  }
 }catch(e){toast(e.message,true)}
}

async function statusAction(type,index){
 try{
  const path=type==="room"?"/room-bookings":"/restaurant/orders";const r=await api(path);const row=r.data?.[Number(index)];if(!row)return;
  const id=type==="room"?row.booking_id:row.order_id;const choices=type==="room"?["Pending","Confirmed","Checked-In","Checked-Out","Cancelled","No-Show"]:["Pending","Preparing","Ready","Served","Completed","Cancelled"];
  formModal("Update Status",[{name:"status",label:"Status",type:"select",options:choices}],async o=>api(`${type==="room"?"/room-bookings/":"/restaurant/orders/"}${encodeURIComponent(id)}/status`,{method:"PATCH",body:JSON.stringify(o)}));
 }catch(e){toast(e.message,true)}
}
async function changeGuestStatus(customerId,targetStatus){
 const labels={Active:"Activate",Inactive:"Deactivate",Blacklisted:"Blacklist"};
 const label=labels[targetStatus]||targetStatus;
 const message=targetStatus==="Blacklisted"
   ? "Blacklist this guest? The guest record and history will be preserved."
   : `${label} this guest?`;
 if(!window.confirm(message))return;
 try{
   await api(`/customers/${encodeURIComponent(customerId)}/status`,{method:"PATCH",body:JSON.stringify({status:targetStatus})});
   toast(`Guest status changed to ${targetStatus}.`);
   document.getElementById("page").innerHTML=`<div class="loading">Refreshing guest…</div>`;
   document.getElementById("page").innerHTML=await guestDetail(customerId);
   bindPageEvents();
 }catch(e){toast(e.message,true)}
}
function openGuestEdit(c){
 if(!isActionAllowed("guest_update")){showAccessDenied();return;}
 return formModal("Edit Guest",[
  {name:"customer_name",label:"Guest name",value:c.customer_name||""},{name:"customer_mobile",label:"Mobile",value:c.customer_mobile||""},{name:"customer_email",label:"Email",required:false,value:c.customer_email||""},{name:"customer_address",label:"Address",required:false,value:c.customer_address||""},{name:"customer_city",label:"City",required:false,value:c.customer_city||""},{name:"customer_state",label:"State",required:false,value:c.customer_state||""},{name:"customer_country",label:"Country",required:false,value:c.customer_country||"India"},{name:"customer_pincode",label:"Pincode",required:false,value:c.customer_pincode||""},{name:"preferences",label:"Preferences",required:false,value:c.preferences||"",full:true},{name:"special_requests",label:"Special requests",required:false,value:c.special_requests||"",full:true},{name:"guest_notes",label:"Guest notes",required:false,value:c.guest_notes||"",full:true}
 ],o=>api(`/customers/${encodeURIComponent(c.customer_id)}`,{method:"PUT",body:JSON.stringify({...o,is_active:o.guest_status!=="Inactive"})}));
}
async function openReservationCreate(){
  if(!isActionAllowed("booking")){
    showAccessDenied();
    return;
  }

  const b=document.createElement("div");
  b.className="modal-backdrop";
  b.innerHTML=`
    <div class="modal">
      <div class="page-head">
        <div>
          <h2>New Room Reservation</h2>
          <span class="section-note">Select an available room and review the automatic booking total.</span>
        </div>
        <button type="button" data-close>✕</button>
      </div>

      <form class="form-grid" data-reservation-form>

        <label>
          Guest name
          <input name="customer_name" required>
        </label>

        <label>
          Mobile
          <input name="customer_mobile" required>
        </label>

        <label>
          Customer ID
          <input name="customer_id" autocomplete="off" placeholder="Enter existing Customer ID">
          <span class="section-note" data-customer-lookup-status aria-live="polite"></span>
        </label>

        <label>
          Check-in date
          <input name="check_in_date" type="date" value="${esc(dateNow())}" required>
        </label>

        <label>
          Nights
          <input name="days" type="number" min="1" max="365" value="1" required>
        </label>

        <label>
          Room number
          <select name="room_number" required disabled>
            <option value="">Select check-in date and nights first</option>
          </select>
        </label>

        <label>
          Room price / night
          <input name="room_price_display" type="text" readonly value="—">
        </label>

        <label>
          Subtotal
          <input name="subtotal_display" type="text" readonly value="—">
        </label>

        <label>
          GST (5%)
          <input name="gst_display" type="text" readonly value="—">
        </label>

        <label>
          Adults
          <input name="adults" type="number" min="1" max="20" value="1" required>
        </label>

        <label>
          Children
          <input name="children" type="number" min="0" max="20" value="0" required>
        </label>

        <label>
          Special requests / notes
          <textarea name="notes" rows="2" placeholder="Any general request or note"></textarea>
        </label>

        <div class="full reservation-services-panel">
          <div class="section-toolbar">
            <div>
              <h3 style="margin:0">Guest Services</h3>
              <p class="section-note">Add celebration, room, dining or transport services for this reservation.</p>
            </div>
          </div>
          <div class="form-grid" style="margin-top:10px">
            <label>
              Service
              <select name="guest_service_select" data-guest-service-select>
                <option value="">No service selected</option>
              </select>
            </label>
            <label>
              Required date / time
              <div class="reservation-datetime-wrap is-empty" data-guest-service-time-wrap>
                <input name="guest_service_required_at" type="datetime-local" data-guest-service-time aria-label="Required date and time">
                <span class="reservation-datetime-placeholder" data-guest-service-time-placeholder aria-hidden="true">DD-MM-YYYY --:--</span>
              </div>
            </label>
            <label class="full">
              Service note
              <input name="guest_service_note" data-guest-service-note placeholder="Example: Rose petals + balloons, ready by 8 PM">
            </label>
            <div class="full form-actions" style="justify-content:flex-start">
              <button type="button" data-add-guest-service>Add Service</button>
            </div>
          </div>
          <div class="section-note" data-guest-services-empty>No guest services added.</div>
          <div data-guest-services-list></div>
          <div class="reservation-service-totals" style="margin-top:12px">
            <div><span>Guest Services Grand Total</span><strong data-guest-services-total>₹0</strong></div>
          </div>
        </div>

        <div class="full reservation-summary">
          <div class="section-toolbar">
            <div>
              <h3 style="margin:0">Reservation Summary</h3>
              <p class="section-note">Room reservation and guest services totals.</p>
            </div>
          </div>
          <div class="reservation-summary-grid">
            <div><span>Room Reservation Total</span><strong data-room-reservation-total>₹0</strong></div>
            <div><span>Guest Services Total</span><strong data-summary-guest-services-total>₹0</strong></div>
            <div class="grand-total"><span>Grand Total</span><strong data-reservation-grand-total>₹0</strong></div>
          </div>
          <div class="reservation-payment-grid">
            <label>
              Advance
              <input name="advance_amount" type="number" min="0" step="0.01" value="0" required>
            </label>
            <label>
              Balance
              <input name="balance_display" type="text" readonly value="₹0">
            </label>
            <label>
              Payment method
              <select name="payment_method" required>
                <option value="Cash">Cash</option>
                <option value="UPI">UPI</option>
                <option value="Card">Card</option>
                <option value="Other">Other</option>
              </select>
            </label>
          </div>
        </div>

        <div class="full form-actions">
          <button type="button" data-close>Cancel</button>
          <button class="primary" type="submit">Save</button>
        </div>

        <p class="form-error full" data-error></p>

      </form>
    </div>`;

  document.body.appendChild(b);

  const form=b.querySelector("[data-reservation-form]");
  const roomSelect=form.elements.room_number;
  const dateInput=form.elements.check_in_date;
  const nightsInput=form.elements.days;
  const customerIdInput=form.elements.customer_id;
  const customerNameInput=form.elements.customer_name;
  const customerMobileInput=form.elements.customer_mobile;
  const customerLookupStatus=b.querySelector("[data-customer-lookup-status]");

  const roomPrice=form.elements.room_price_display;
  const subtotal=form.elements.subtotal_display;
  const gst=form.elements.gst_display;
  const roomReservationTotalDisplay=b.querySelector("[data-room-reservation-total]");
  const summaryGuestServicesTotal=b.querySelector("[data-summary-guest-services-total]");
  const reservationGrandTotalDisplay=b.querySelector("[data-reservation-grand-total]");

  const advance=form.elements.advance_amount;
  const balance=form.elements.balance_display;

  const error=b.querySelector("[data-error]");

  let availableRooms=[];
  let loadingRooms=false;
  let linkedCustomerId="";
  let customerLookupTimer=null;
  let customerLookupToken=0;
  let guestServiceCatalog=[];
  let guestServices=[];

  b.querySelectorAll("[data-close]").forEach(x=>{
    x.onclick=()=>b.remove();
  });

  const setError=msg=>{
    error.textContent=msg||"";
  };

  const setCustomerLookupStatus=(msg,isError=false)=>{
    if(!customerLookupStatus)return;
    customerLookupStatus.textContent=msg||"";
    customerLookupStatus.style.color=isError?"var(--danger,#b42318)":"";
  };

  const setLinkedGuestFields=(linked)=>{
    customerNameInput.readOnly=Boolean(linked);
    customerMobileInput.readOnly=Boolean(linked);
  };

  const clearLinkedGuest=({clearFields=true}={})=>{
    linkedCustomerId="";
    setLinkedGuestFields(false);
    if(clearFields){
      customerNameInput.value="";
      customerMobileInput.value="";
    }
  };

  const lookupGuestById=async({showStatus=true}={})=>{
    const customerId=String(customerIdInput.value||"").trim().toUpperCase();

    if(!customerId){
      clearLinkedGuest();
      setCustomerLookupStatus("");
      return true;
    }

    if(customerId===linkedCustomerId){
      return true;
    }

    const token=++customerLookupToken;
    if(showStatus)setCustomerLookupStatus("Looking up guest…");

    try{
      const response=await api(`/customers/${encodeURIComponent(customerId)}`);
      if(token!==customerLookupToken)return false;

      const customer=response?.data?.customer||{};
      const resolvedId=String(customer.customer_id||customerId).trim().toUpperCase();

      if(!customer.customer_name||!customer.customer_mobile){
        clearLinkedGuest();
        setCustomerLookupStatus("Guest record is missing name or mobile.",true);
        return false;
      }

      customerIdInput.value=resolvedId;
      customerNameInput.value=String(customer.customer_name||"");
      customerMobileInput.value=String(customer.customer_mobile||"");
      linkedCustomerId=resolvedId;
      setLinkedGuestFields(true);
      setCustomerLookupStatus("Guest linked successfully.");
      return true;
    }catch(err){
      if(token!==customerLookupToken)return false;
      clearLinkedGuest();
      setCustomerLookupStatus(err.message||"Guest not found.",true);
      return false;
    }
  };

  const scheduleGuestLookup=()=>{
    window.clearTimeout(customerLookupTimer);
    const customerId=String(customerIdInput.value||"").trim().toUpperCase();

    if(customerId!==linkedCustomerId){
      clearLinkedGuest();
      setCustomerLookupStatus("");
    }

    if(!customerId)return;

    customerLookupTimer=window.setTimeout(()=>{
      lookupGuestById();
    },450);
  };

  customerIdInput.addEventListener("input",scheduleGuestLookup);
  customerIdInput.addEventListener("blur",()=>lookupGuestById());
  customerIdInput.addEventListener("keydown",event=>{
    if(event.key==="Enter"){
      event.preventDefault();
      window.clearTimeout(customerLookupTimer);
      lookupGuestById();
    }
  });

  const guestServiceSelect=form.elements.guest_service_select;
  const guestServiceTime=form.elements.guest_service_required_at;
  const guestServiceTimeWrap=b.querySelector("[data-guest-service-time-wrap]");
  const guestServiceTimePlaceholder=b.querySelector("[data-guest-service-time-placeholder]");
  const guestServiceNote=form.elements.guest_service_note;
  const guestServicesList=b.querySelector("[data-guest-services-list]");
  const guestServicesEmpty=b.querySelector("[data-guest-services-empty]");
  const guestServicesTotal=b.querySelector("[data-guest-services-total]");

  const renderGuestServices=()=>{
    guestServicesEmpty.style.display=guestServices.length?"none":"block";
    guestServicesList.innerHTML=guestServices.map((item,index)=>`
      <div class="card" style="margin-top:8px;padding:10px 12px">
        <div class="section-toolbar">
          <div><strong>${esc(item.service_name)}</strong><div class="section-note">${esc(item.service_type)} · ${item.price>0?money(item.price):"Free"}</div></div>
          <button type="button" data-remove-guest-service="${index}">Remove</button>
        </div>
        ${item.required_at?`<div class="section-note">Required: ${esc(item.required_at)}</div>`:""}
        ${item.note?`<div class="section-note">${esc(item.note)}</div>`:""}
      </div>`).join("");
    guestServicesList.querySelectorAll("[data-remove-guest-service]").forEach(btn=>btn.onclick=()=>{guestServices.splice(Number(btn.dataset.removeGuestService),1);renderGuestServices();updateTotals()});
  };

  const loadGuestServiceCatalog=async()=>{
    try{
      const r=await api("/guest-services/catalog");
      guestServiceCatalog=Array.isArray(r.data)?r.data:[];
      guestServiceSelect.innerHTML='<option value="">No service selected</option>'+guestServiceCatalog.map(x=>`<option value="${esc(x.service_id)}">${esc(x.service_name)} — ${x.billing_mode==="Free"?"Free":x.billing_mode==="Quote"?"Quote":money(x.price)} · ${esc(x.billing_mode||"Reservation Bill")}</option>`).join("");
    }catch(e){
      guestServiceCatalog=[];
      guestServiceSelect.innerHTML='<option value="">Guest services unavailable</option>';
    }
  };

  b.querySelector("[data-add-guest-service]")?.addEventListener("click",()=>{
    const service=guestServiceCatalog.find(x=>String(x.service_id)===String(guestServiceSelect.value));
    if(!service){setError("Select a guest service first.");return;}
    guestServices.push({service_id:Number(service.service_id),service_name:service.service_name,service_type:service.service_type,price:Number(service.price||0),pricing_mode:service.pricing_mode||"Paid",billing_mode:service.billing_mode||"Reservation Bill",required_at:guestServiceTime.value||"",note:guestServiceNote.value.trim()||service.service_name});
    guestServiceSelect.value=""; guestServiceTime.value=""; guestServiceNote.value=""; setError(""); renderGuestServices(); updateTotals();
  });
  renderGuestServices();

  const selectedRoom=()=>{
    const roomNo=roomSelect.value;

    return availableRooms.find(
      r=>String(r.room_number)===String(roomNo)
    )||null;
  };

  const updateTotals=()=>{
    const room=selectedRoom();

    const price=Number(room?.room_price||0);
    const nights=Math.max(
      1,
      Number(nightsInput.value||1)
    );

    const sub=price*nights;
    const tax=Number((sub*0.05).toFixed(2));
    const roomTotal=Number((sub+tax).toFixed(2));
    const serviceTotal=guestServices.filter(x=>x.billing_mode==="Reservation Bill").reduce((sum,x)=>sum+Number(x.price||0),0);
    const reservationTotal=Number((roomTotal+serviceTotal).toFixed(2));

    roomPrice.value=price ? money(price) : "—";
    subtotal.value=price ? money(sub) : "—";
    gst.value=price ? money(tax) : "—";

    const paid=Math.max(0,Number(advance.value||0));
    if(paid>reservationTotal){
      advance.value=reservationTotal;
    }
    const effectivePaid=Math.max(0,Number(advance.value||0));

    balance.value=(room||serviceTotal>0)
      ? money(Math.max(0,reservationTotal-effectivePaid))
      : "—";

    if(guestServicesTotal){ guestServicesTotal.textContent=money(serviceTotal); }
    if(roomReservationTotalDisplay){ roomReservationTotalDisplay.textContent=money(roomTotal); }
    if(summaryGuestServicesTotal){ summaryGuestServicesTotal.textContent=money(serviceTotal); }
    if(reservationGrandTotalDisplay){ reservationGrandTotalDisplay.textContent=money(reservationTotal); }
  };

  const loadRooms=async()=>{
    const date=dateInput.value||dateNow();

    const nights=Math.max(
      1,
      Math.min(365,Number(nightsInput.value||1))
    );

    nightsInput.value=nights;

    const previousRoom=roomSelect.value;

    roomSelect.disabled=true;
    roomSelect.innerHTML=
      '<option value="">Loading available rooms…</option>';

    availableRooms=[];
    updateTotals();
    setError("");
    loadingRooms=true;

    try{
      const r=await api(
        `/rooms/availability?check_in_date=${encodeURIComponent(date)}&nights=${nights}`
      );

      availableRooms=Array.isArray(r.data)
        ? r.data
        : [];

      roomSelect.innerHTML=availableRooms.length
        ? `<option value="">Select available room</option>`+
          availableRooms.map(room=>{
            const no=esc(room.room_number);
            const type=esc(room.room_type||"Room");
            const price=money(room.room_price);

            return `
              <option value="${no}">
                ${no} — ${type} — ${price}/night
              </option>`;
          }).join("")
        : '<option value="">No rooms available for selected dates</option>';

      if(
        previousRoom &&
        availableRooms.some(
          r=>String(r.room_number)===String(previousRoom)
        )
      ){
        roomSelect.value=previousRoom;
      }

      roomSelect.disabled=availableRooms.length===0;

      updateTotals();

    }catch(e){

      availableRooms=[];

      roomSelect.innerHTML=
        '<option value="">Could not load available rooms</option>';

      roomSelect.disabled=true;

      setError(e.message);
      updateTotals();

    }finally{
      loadingRooms=false;
    }
  };

  dateInput.min=dateNow();
  dateInput.addEventListener("change",()=>{
    const today=dateNow();
    if(dateInput.value && dateInput.value<today){
      dateInput.value=today;
      setError("Check-in date cannot be earlier than today.");
    }else{
      setError("");
    }
    loadRooms();
  });

  nightsInput.addEventListener("input",()=>{
    if(Number(nightsInput.value||0)<1){
      nightsInput.value=1;
    }

    loadRooms();
  });

  roomSelect.addEventListener("change",()=>{
    updateTotals();
  });

  advance.addEventListener("input",()=>{
    const room=selectedRoom();
    const serviceTotal=guestServices.filter(x=>x.billing_mode==="Reservation Bill").reduce((sum,x)=>sum+Number(x.price||0),0);
    const roomTotal=room
      ? Number((Number(room.room_price||0)*Number(nightsInput.value||1)*1.05).toFixed(2))
      : 0;
    const total=Number((roomTotal+serviceTotal).toFixed(2));
    let paid=Math.max(0,Number(advance.value||0));
    if(paid>total){
      paid=total;
      advance.value=total;
    }
    balance.value=(room||serviceTotal>0)
      ? money(Math.max(0,total-paid))
      : "—";
  });

  const syncGuestServiceDatePlaceholder=()=>{
    const hasValue=Boolean(guestServiceTime.value);
    guestServiceTimeWrap?.classList.toggle("is-empty",!hasValue);
    guestServiceTimePlaceholder?.classList.toggle("is-hidden",hasValue);
  };
  guestServiceTime.addEventListener("input",syncGuestServiceDatePlaceholder);
  guestServiceTime.addEventListener("change",syncGuestServiceDatePlaceholder);
  guestServiceTime.addEventListener("focus",()=>guestServiceTimeWrap?.classList.add("is-focused"));
  guestServiceTime.addEventListener("blur",()=>guestServiceTimeWrap?.classList.remove("is-focused"));
  syncGuestServiceDatePlaceholder();

  form.onsubmit=async e=>{
    e.preventDefault();
    setError("");

    if(loadingRooms){
      setError("Please wait while available rooms are loading.");
      return;
    }

    const room=selectedRoom();

    if(!room){
      setError("Please select an available room.");
      return;
    }

    const checkInDate=String(dateInput.value||"").trim();
    if(!checkInDate || checkInDate<dateNow()){
      setError("Check-in date cannot be earlier than today.");
      dateInput.focus();
      return;
    }

    if(String(customerIdInput.value||"").trim()){
      const linked=await lookupGuestById();
      if(!linked){
        setError("Please enter a valid Customer ID or clear it and enter guest details manually.");
        customerIdInput.focus();
        return;
      }
    }

    const nights=Math.max(
      1,
      Number(nightsInput.value||1)
    );

    const roomTotal=Number(
      (
        Number(room.room_price||0) *
        nights *
        1.05
      ).toFixed(2)
    );
    const serviceTotal=guestServices.filter(x=>x.billing_mode==="Reservation Bill").reduce((sum,x)=>sum+Number(x.price||0),0);
    const total=Number((roomTotal+serviceTotal).toFixed(2));

    const paid=Number(advance.value||0);

    if(paid<0){
      setError("Advance cannot be negative.");
      return;
    }

    if(paid>total){
      setError(
        "Advance payment cannot be greater than the reservation grand total."
      );
      return;
    }

    const fd=new FormData(form);

    const payload={
      customer_name:String(
        fd.get("customer_name")||""
      ).trim(),

      customer_mobile:String(
        fd.get("customer_mobile")||""
      ).trim(),

      customer_id:String(
        fd.get("customer_id")||""
      ).trim()||undefined,

      room_number:room.room_number,

      days:nights,

      check_in_date:String(
        fd.get("check_in_date")||""
      ),

      advance_amount:paid,

      payment_method:String(
        fd.get("payment_method")||"Cash"
      ),

      adults:Number(
        fd.get("adults")||1
      ),

      children:Number(
        fd.get("children")||0
      ),

      notes:String(
        fd.get("notes")||""
      ).trim()
    };

    try{

      const bookingResult=await api("/room-bookings",{
        method:"POST",
        body:JSON.stringify(payload)
      });

      const createdBookingId=bookingResult?.data?.booking_id||"";
      let serviceFailure="";
      for(const service of guestServices){
        try{
          await api("/guest-services/requests",{
            method:"POST",
            body:JSON.stringify({
              booking_id:createdBookingId||undefined,
              customer_id:payload.customer_id||undefined,
              guest_name:payload.customer_name,
              room_number:payload.room_number,
              service_id:service.service_id,
              service_type:service.service_type,
              service_name:service.service_name,
              description:service.note||service.service_name,
              required_at:service.required_at||undefined,
              price:service.price,
              payment_status:service.price>0?"Pending":"Not Required",
              billing_mode:service.billing_mode,
              priority:"Normal"
            })
          });
        }catch(err){serviceFailure=err?.message||"A guest service could not be created.";}
      }

      b.remove();
      toast(serviceFailure?`Reservation created, but a guest service could not be added: ${serviceFailure}`:"Room reservation created successfully.",Boolean(serviceFailure));
      render();

    }catch(err){

      setError(err.message);

    }
  };

  await Promise.all([loadRooms(),loadGuestServiceCatalog()]);
}
function openAction(a){
 if(a==="room_create")return formModal("Add Room",[
  {name:"room_number",label:"Room number"},
  {name:"room_type",label:"Room type"},
  {name:"floor",label:"Floor",type:"number"},
  {name:"capacity",label:"Capacity",type:"number"},
  {name:"room_price",label:"Room price",type:"number"},
  {name:"amenities",label:"Amenities",required:false,full:true},
  {name:"description",label:"Description",required:false,full:true}
],o=>api("/rooms",{
  method:"POST",
  body:JSON.stringify({
    room_number:o.room_number,
    room_type:o.room_type,
    floor:Number(o.floor),
    capacity:Number(o.capacity),
    room_price:Number(o.room_price),
    amenities:o.amenities||"",
    description:o.description||""
  })
}));
 if(a==="customer")return formModal("New Guest",[
  {name:"customer_name",label:"Guest name"},
  {name:"customer_mobile",label:"Mobile"},
  {name:"customer_email",label:"Email",required:false},
  {name:"customer_address",label:"Address",required:false,full:true},
  {name:"customer_city",label:"City",required:false},
  {name:"customer_state",label:"State",required:false},
  {name:"customer_country",label:"Country",required:false,value:"India"},
  {name:"customer_pincode",label:"Pincode",required:false},
  {name:"government_id_type",label:"Government ID Type (optional for profile creation)",type:"select",options:["", "Aadhaar Card", "Driving Licence", "Voter ID Card", "Passport", "Other Government ID"],required:false},
  {name:"government_id_status",label:"ID Verification Status",type:"select",options:["Not Provided", "Pending Verification", "Verified", "Rejected"],value:"Not Provided",required:false},
  {name:"government_id_document",label:"Government ID Document (PDF/JPG/PNG, max 800 KB)",type:"file",accept:".pdf,.jpg,.jpeg,.png",required:false,full:true},
  {name:"preferences",label:"Preferences",required:false,full:true},
  {name:"special_requests",label:"Special requests",required:false,full:true},
  {name:"guest_notes",label:"Notes",required:false,full:true}
 ],o=>api("/customers",{method:"POST",body:JSON.stringify(o)}));
if(a==="booking")return openReservationCreate();
 if(a==="order")return openRestaurantOrderModal();
 if(a==="expense")return formModal("New Expense",[
  {name:"expense_id",label:"Expense ID"},{name:"expense_date",label:"Date",type:"date"},{name:"expense_time",label:"Time",placeholder:"HH:MM"},{name:"expense_name",label:"Expense name"},{name:"amount",label:"Amount",type:"number"},{name:"category",label:"Category"},{name:"category_id",label:"Category ID",required:false},{name:"vendor_id",label:"Vendor / Supplier ID",required:false},{name:"payment_method",label:"Payment method",type:"select",options:["Cash","Card","UPI","Online","Bank Transfer","Cheque","Other"]},{name:"receipt_reference",label:"Receipt / Reference",required:false},{name:"department_id",label:"Department ID",required:false},{name:"description",label:"Description"},{name:"is_recurring",label:"Recurring",type:"select",options:["false","true"],value:"false"},{name:"recurrence_frequency",label:"Recurrence frequency",type:"select",options:["","Daily","Weekly","Monthly","Quarterly","Yearly"],required:false},{name:"recurrence_start_date",label:"Recurrence start date",type:"date",required:false}
 ],o=>api("/expenses",{method:"POST",body:JSON.stringify({...o,amount:Number(o.amount),is_recurring:String(o.is_recurring).toLowerCase()==="true",recurrence_frequency:o.recurrence_frequency||undefined,recurrence_start_date:o.recurrence_start_date||undefined})}));
 if(a==="transport")return formModal("Transportation Request",[
  {name:"customer_id",label:"Customer ID",required:false},{name:"guest_name",label:"Guest name",required:false},{name:"guest_mobile",label:"Mobile",required:false},{name:"transportation_type",label:"Type",type:"select",options:["Airport Pickup","Airport Drop","Railway Station Pickup","Railway Station Drop","Local Transportation","Taxi / Cab Request"]},
  {name:"pickup_date",label:"Pickup date",type:"date"},{name:"pickup_time",label:"Pickup time"},{name:"pickup_location",label:"Pickup location"},{name:"drop_location",label:"Drop location"},{name:"vehicle_type",label:"Vehicle type",required:false},{name:"fare",label:"Fare",type:"number",required:false},{name:"special_request",label:"Special request",required:false,full:true},{name:"notes",label:"Notes",required:false,full:true}
 ],o=>api("/transportation/requests",{method:"POST",body:JSON.stringify(o)}));
}
async function render(){
  buildNav();
  setTop();
  setActive();
  refreshNotificationBadge();
  await renderPage();
  buildNav();
  setActive();
  setTop();
}
function connectionBanner(){
  let b=document.getElementById("connection-banner");
  if(!b){b=document.createElement("div");b.id="connection-banner";b.className="connection-banner hidden";b.textContent="Offline — reconnecting…";document.body.appendChild(b);}
  b.classList.toggle("hidden", navigator.onLine);
}
window.addEventListener("online", connectionBanner);
window.addEventListener("offline", connectionBanner);

async function boot(){
 buildNav();
 document.getElementById("login-form").onsubmit=async e=>{e.preventDefault();const err=document.getElementById("login-error");err.textContent="";try{const payload={username:document.getElementById("login-username").value.trim(),password:document.getElementById("login-password").value};const h=document.getElementById("login-hotel").value;if(h)payload.hotel_id=Number(h);const r=await api("/auth/login",{method:"POST",body:JSON.stringify(payload)});persistAuth(r.access_token,r.user,r.expires_in);state.hotelContext=(await api("/hotel/context")).data||null;const perm=await api("/auth/permissions");state.user.permissions=perm.data||[];prepareRoleLanding();buildNav();showDashboard();await render()}catch(e){err.textContent=e.message}};
 document.getElementById("logout-btn").onclick=()=>forceLogout("");
  document.getElementById("kitchen-logout-btn").onclick=()=>forceLogout("");
 document.getElementById("user-btn").onclick=()=>openUserProfile();
 document.getElementById("notification-btn").onclick=()=>{if(!canOpenPage("notifications")){showAccessDenied();return;}state.page="notifications";closeSidebar();render()};
 document.getElementById("refresh-btn").onclick=render;
 document.getElementById("menu-toggle").onclick=()=>document.getElementById("sidebar").classList.contains("open")?closeSidebar():openSidebar();
 document.getElementById("sidebar-close").onclick=closeSidebar;
 document.getElementById("sidebar-overlay").onclick=closeSidebar;
 window.addEventListener("keydown",e=>{if(e.key==="Escape" && state.page==="rooms"){state.page="dashboard";render()}});
 window.addEventListener("resize",()=>{if(window.innerWidth>800)closeSidebar()});
 if(state.token && !storedTokenIsExpired()){restoreAuthTimer();try{state.user=(await api("/auth/me")).data;const perm=await api("/auth/permissions");state.user.permissions=perm.data||[];prepareRoleLanding();buildNav();showDashboard();state.hotelContext=(await api("/hotel/context")).data||null;await render()}catch{forceLogout("")}}else{clearAuth();showLogin("");}
  bindExpenseEvents();
}
boot();

window.addEventListener("error", () => toast("Unexpected dashboard error. Please refresh the page.", true));
window.addEventListener("unhandledrejection", () => toast("A dashboard operation failed. Please try again.", true));
