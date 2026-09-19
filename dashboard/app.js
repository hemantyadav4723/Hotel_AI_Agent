const DASHBOARD_CONFIG = window.YH_DASHBOARD_CONFIG || {apiBase:"/api/v1", requestTimeoutMs:15000};
const API = DASHBOARD_CONFIG.apiBase.replace(/\/$/,"");
const SESSION = window.sessionStorage;
const state = { token: SESSION.getItem("yh_access_token") || "", user: null, hotelContext: null, page: "dashboard", data: null, listPages: {} };

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
function dateNow(){return new Date().toISOString().slice(0,10);}
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
  if(!res.ok) throw new Error(body.detail||`Request failed (${res.status})`);
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
function showLogin(msg=""){document.getElementById("login-view").classList.remove("hidden");document.getElementById("dashboard-view").classList.add("hidden");document.getElementById("login-error").textContent=msg;}
function showDashboard(){document.getElementById("login-view").classList.add("hidden");document.getElementById("dashboard-view").classList.remove("hidden");}
function normalizePermissionName(value){return String(value??"").trim().toLowerCase().replace(/\s+/g,"_");}
function currentRole(){return normalizePermissionName(state.user?.role??state.user?.role_name??"");}
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
function canOpenPage(pageId){const spec=NAV_PERMISSION_MAP[pageId];if(!spec)return isAdmin();return hasPermission(spec[0],spec[1]);}
const ACTION_PERMISSION_MAP={
 customer:["Customers","Create"], booking:["Rooms","Create"], order:["Restaurant","Create"], expense:["Expenses","Create"], feedback_update:["Customers","Update"], maps_config:["Hotel","Update"], nearby_create:["Hotel","Create"], nearby_status:["Hotel","Update"], route_create:["Hotel","Create"], media_create:["Hotel","Create"], media_update:["Hotel","Update"], media_status:["Hotel","Update"], transport:["Hotel","Create"], transport_update:["Hotel","Update"],
 backup:["Users","Create"], guest_update:["Customers","Update"], room_status:["Rooms","Update"], order_status:["Restaurant","Update"], inventory_stock:["Inventory","Create"], notification_read:["Reports","Update"]
};
function isActionAllowed(actionName){const spec=ACTION_PERMISSION_MAP[actionName];if(!spec)return isAdmin();return hasPermission(spec[0],spec[1]);}
function showAccessDenied(){document.getElementById("page").innerHTML=`${pageHead("Access Restricted","Your current role does not have permission to view this module.")}<div class="card danger"><h3>Permission required</h3><p class="section-note">Ask an administrator to grant the required permission. The FastAPI backend remains the final authorization boundary.</p></div>`;}
function buildNav(){const nav=document.getElementById("nav");nav.innerHTML="";NAV.forEach(group=>{const allowed=group.items.filter(([id])=>canOpenPage(id));if(!allowed.length)return;const sec=document.createElement("div");sec.className="nav-section";sec.textContent=group.section;nav.appendChild(sec);allowed.forEach(([id,icon,label])=>{const b=document.createElement("button");b.className="nav-item";b.dataset.page=id;b.innerHTML=`<span class="nav-icon">${icon}</span><span>${esc(label)}</span>`;b.onclick=()=>{if(!canOpenPage(id)){showAccessDenied();return;}state.page=id;render();document.getElementById("sidebar").classList.remove("open")};nav.appendChild(b)})})}
function setTop(){const labels={};NAV.forEach(g=>g.items.forEach(x=>labels[x[0]]=x[2]));const label=labels[state.page]||"Dashboard";const crumb=document.getElementById("breadcrumb");if(crumb)crumb.textContent=state.page==="dashboard"?"Dashboard":`Dashboard / ${label}`;if(state.user){document.getElementById("user-label").textContent=state.user.username||"User";document.getElementById("user-avatar").textContent=(state.user.username||"U")[0].toUpperCase();const h=state.hotelContext||{};const label=h.hotel_name?`${h.hotel_name} • ${h.hotel_code||`Hotel ID ${state.user.hotel_id}`}`:(state.user.hotel_id?`Hotel ID ${state.user.hotel_id}`:"Hotel context");document.getElementById("hotel-context").textContent=label}}
async function refreshNotificationBadge(){const el=document.getElementById("notification-count");if(!el||!state.token)return;try{const r=await api("/notifications?unread_only=true&limit=1");const count=Number(r.data?.length||0);el.textContent=count>99?"99+":String(count);el.classList.toggle("hidden",count===0)}catch{el.classList.add("hidden")}}
function closeSidebar(){document.getElementById("sidebar")?.classList.remove("open");document.getElementById("sidebar-overlay")?.classList.add("hidden");}
function openSidebar(){document.getElementById("sidebar")?.classList.add("open");document.getElementById("sidebar-overlay")?.classList.remove("hidden");}
function openUserProfile(){const u=state.user||{};const b=document.createElement("div");b.className="modal-backdrop";b.innerHTML=`<div class="modal profile-modal"><div class="page-head"><div><h2>User Profile</h2><span class="section-note">Current dashboard session</span></div><button data-close>✕</button></div><div class="profile-grid"><div class="profile-avatar">${esc((u.username||"U")[0].toUpperCase())}</div><div><strong>${esc(u.username||"User")}</strong><p class="section-note">Role: ${esc(u.role||"—")}</p><p class="section-note">Hotel: ${esc(u.hotel_id??"—")}</p><p class="section-note">Staff: ${esc(u.staff_name||"—")}</p></div></div><div class="form-actions"><button data-close>Close</button><button class="primary" data-password>Change Password</button></div></div>`;document.body.appendChild(b);b.querySelectorAll("[data-close]").forEach(x=>x.onclick=()=>b.remove());b.querySelector("[data-password]").onclick=()=>{b.remove();openPasswordChange()};}

function setActive(){document.querySelectorAll(".nav-item").forEach(x=>x.classList.toggle("active",x.dataset.page===state.page));}
function showObjectModal(title,obj){const b=document.createElement("div");b.className="modal-backdrop";b.innerHTML=`<div class="modal"><div class="page-head"><div><h2>${esc(title)}</h2><span class="section-note">Read-only details</span></div><button data-close>✕</button></div>${table([obj])}<div class="form-actions"><button data-close>Close</button></div></div>`;document.body.appendChild(b);b.querySelectorAll("[data-close]").forEach(x=>x.onclick=()=>b.remove())}
function table(rows,actions=""){
  if(!Array.isArray(rows)||!rows.length)return `<div class="empty">No records found.</div>`;
  const keys=[...new Set(rows.flatMap(r=>Object.keys(r||{})))].slice(0,12);
  const head=keys.map(k=>`<th>${esc(k.replaceAll("_"," "))}</th>`).join("")+(actions?`<th>Actions</th>`:"");
  const body=rows.map((r,i)=>`<tr>${keys.map(k=>`<td>${cell(r[k])}</td>`).join("")}${actions?`<td>${actions.replaceAll("{{i}}",i)}</td>`:""}</tr>`).join("");
  return `<div class="table-wrap"><table class="data-table"><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table></div>`;
}
function paginatedTable(rows,actions="",key="list",pageSize=25){
  if(!Array.isArray(rows)||!rows.length)return `<div class="empty">No records found.</div>`;
  const total=rows.length, pages=Math.max(1,Math.ceil(total/pageSize));
  const current=Math.min(Math.max(1,Number(state.listPages[key]||1)),pages); state.listPages[key]=current;
  const start=(current-1)*pageSize, visible=rows.slice(start,start+pageSize);
  const keys=[...new Set(rows.flatMap(r=>Object.keys(r||{})))].slice(0,12);
  const head=keys.map(k=>`<th>${esc(k.replaceAll("_"," "))}</th>`).join("")+(actions?`<th>Actions</th>`:"");
  const body=visible.map((r,i)=>{const idx=start+i;return `<tr>${keys.map(k=>`<td>${cell(r[k])}</td>`).join("")}${actions?`<td>${actions.replaceAll("{{i}}",idx)}</td>`:""}</tr>`}).join("");
  const nav=pages>1?`<div class="pagination" role="navigation" aria-label="Pagination"><button type="button" data-page-prev="${esc(key)}" ${current===1?"disabled":""}>Previous</button><span>Page ${current} of ${pages} · ${start+1}-${Math.min(start+pageSize,total)} of ${total}</span><button type="button" data-page-next="${esc(key)}" ${current===pages?"disabled":""}>Next</button></div>`:"";
  return `<div class="table-wrap"><table class="data-table"><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table></div>${nav}`;
}
function cell(v){if(v===null||v===undefined)return "—";if(typeof v==="object")return esc(JSON.stringify(v));const s=String(v);if(s.length>90)return `<span title="${esc(s)}">${esc(s.slice(0,87))}…</span>`;return esc(s);}
async function listCard(title,path,opts={}){const r=await api(path);const rows=r.data||[];return `<div class="card"><div class="page-head"><div><h3>${esc(title)}</h3><span class="section-note">${rows.length} record(s)</span></div>${opts.action||""}</div>${table(rows,opts.actions||"")}</div>`}
function formModal(title,fields,onSubmit){const b=document.createElement("div");b.className="modal-backdrop";b.innerHTML=`<div class="modal"><div class="page-head"><div><h2>${esc(title)}</h2><span class="section-note">Enter validated information</span></div><button data-close>✕</button></div><form class="form-grid">${fields.map(f=>`<label class="${f.full?'full':''}">${esc(f.label)}${f.type==="select"?`<select name="${esc(f.name)}">${(f.options||[]).map(o=>`<option value="${esc(o)}" ${String(o)===String(f.value??"")?"selected":""}>${esc(o)}</option>`).join("")}</select>`:`<input name="${esc(f.name)}" type="${f.type||"text"}" ${f.required===false?"":"required"} ${f.value!==undefined?`value="${esc(f.value)}"`:""} ${f.placeholder?`placeholder="${esc(f.placeholder)}"`:""}>`}</label>`).join("")}<div class="full form-actions"><button type="button" data-close>Cancel</button><button class="primary" type="submit">Save</button></div><p class="form-error full" data-error></p></form></div>`;document.body.appendChild(b);b.querySelectorAll("[data-close]").forEach(x=>x.onclick=()=>b.remove());b.querySelector("form").onsubmit=async e=>{e.preventDefault();const fd=new FormData(e.target),obj={};fields.forEach(f=>{let v=fd.get(f.name);if(f.type==="number"&&v!=="")v=Number(v);obj[f.name]=v||undefined});try{await onSubmit(obj);b.remove();toast("Saved successfully.");render()}catch(err){b.querySelector("[data-error]").textContent=err.message}}}
function pageHead(title,sub="",actions=""){return `<div class="page-head"><div><h1>${esc(title)}</h1><div class="section-note">${esc(sub)}</div></div><div class="actions">${actions}</div></div>`}
async function dashboard(){
  const d=(await api("/dashboard/home")).data||{};
  return pageHead("Dashboard","Today's hotel operating summary",`<button class="primary" data-refresh>Refresh</button>`)
    +`<div class="grid cards">
      ${metric("Today's Revenue",money(d.total_revenue),`Room ${money(d.room_revenue)} • Restaurant ${money(d.restaurant_revenue)}`)}
      ${metric("Today's Bookings",d.bookings,"Reservations for today")}
      ${metric("Today's Check-ins",d.check_ins,"Expected/recorded arrivals")}
      ${metric("Today's Check-outs",d.check_outs,"Expected departures")}
      ${metric("Occupancy",Number(d.occupancy_pct||0).toFixed(1)+"%",`${d.occupied_rooms||0} occupied / ${d.total_rooms||0} rooms`)}
      ${metric("Restaurant Orders",d.restaurant_orders,"Today's non-cancelled orders")}
      ${metric("Pending Payments",d.pending_payments,"Outstanding room/order balances")}
      ${metric("Low-stock Alerts",d.low_stock_alerts,"Items at or below reorder level")}
      ${metric("Guest Issues",d.pending_guest_issues,"Open complaint/issue records")}
      ${metric("Transportation",d.transportation_requests,"Active transportation requests")}
    </div>
    <div class="grid two" style="margin-top:15px">
      <div class="card"><h3>Hotel Overview</h3><div class="kpi-row">${metric("Total Rooms",d.total_rooms,"Active room inventory")}${metric("Available",d.available_rooms,"Not currently occupied")}</div></div>
      <div class="card"><h3>Quick Actions</h3><div class="kpi-row" style="margin-top:14px">
        <button data-action="customer">+ Guest</button><button data-action="booking">+ Reservation</button><button data-action="expense">+ Expense</button><button data-action="transport">+ Transport</button>
      </div></div>
    </div>`;
}
function metric(label,value,sub){return `<div class="card metric"><div class="label">${esc(label)}</div><div class="value">${esc(value)}</div><div class="sub">${esc(sub)}</div></div>`}
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
  const [p,c,m,media,s]=await Promise.all([
    api("/hotel/profile"),
    api("/hotel/context"),
    api("/hotel/maps"),
    api("/hotel/media"),
    api("/hotel/settings")
  ]);
  const info=p.data||{};
  const context=c.data||{};
  const map=m.data||{};
  const mediaRows=Array.isArray(media.data)?media.data:[];
  const settings=Array.isArray(s.data)?s.data:[];
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
    card("Guest Services",`<div class="section-note">Guest-service availability is represented by the existing facility and hotel master data.</div>${table(facilitiesRows)}`,"Existing service foundation")+
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
 const params=new URLSearchParams(); if(q)params.set("search",q); params.set("search_field",field); if(status)params.set("guest_status",status);
 const rows=(await api("/customers?"+params.toString())).data||[];
 const actions=`<button data-guest-detail="{{i}}">View</button>${isActionAllowed("guest_update")?` <button data-guest-edit="{{i}}">Edit</button>`:""}`;
 return pageHead("Guests & Customers","Guest master, profiles, relationships and complete guest history",`<button class="primary" data-action="customer">+ New Guest</button>`)+
 `<div class="toolbar guest-toolbar"><input class="search" id="guest-search" placeholder="Search name, mobile, ID, email…" value="${esc(q)}"><select id="guest-search-field"><option value="all" ${field==="all"?"selected":""}>All fields</option><option value="id" ${field==="id"?"selected":""}>Customer ID</option><option value="name" ${field==="name"?"selected":""}>Name</option><option value="mobile" ${field==="mobile"?"selected":""}>Mobile</option><option value="email" ${field==="email"?"selected":""}>Email</option><option value="city" ${field==="city"?"selected":""}>City</option><option value="state" ${field==="state"?"selected":""}>State</option></select><select id="guest-status-filter"><option value="" ${!status?"selected":""}>All statuses</option><option value="Active" ${status==="Active"?"selected":""}>Active</option><option value="Inactive" ${status==="Inactive"?"selected":""}>Inactive</option><option value="Blacklisted" ${status==="Blacklisted"?"selected":""}>Blacklisted</option></select><button id="guest-search-btn">Search</button><button id="guest-clear-btn">Clear</button></div>`+
 `<div class="card"><div class="page-head"><div><h3>Guest List</h3><span class="section-note">${rows.length} hotel guest(s)</span></div></div>${table(rows,actions)}</div>`;
}
async function guestDetail(customerId){
 const r=(await api(`/customers/${encodeURIComponent(customerId)}`)).data||{}, c=r.customer||{};
 return pageHead(`Guest: ${c.customer_name||c.customer_id||"Guest"}`,`Customer ID ${c.customer_id||"—"}`,`<button data-back-guests>Back to Guests</button>${isActionAllowed("guest_update")?` <button class="primary" data-edit-current="${esc(c.customer_id)}">Edit Guest</button>`:""}`)+
 `<div class="grid cards">${metric("Total Stays",r.stay_summary?.total_stays||0,"Completed stays")}${metric("Total Bookings",r.booking_summary?.total_bookings||0,"Room reservations")}${metric("Restaurant Orders",r.restaurant_summary?.total_orders||0,"Non-cancelled orders")}${metric("Total Spend",money(Number(r.stay_summary?.total_spend||0)+Number(r.restaurant_summary?.total_spend||0)),"Room + restaurant")}${metric("Lifecycle",r.lifecycle?.lifecycle_stage||r.lifecycle?.stage||"—","Guest lifecycle")}</div>`+
 `<div class="grid two" style="margin-top:15px"><div class="card"><h3>Guest Profile</h3>${table([c])}</div><div class="card"><h3>Hotel Relationship</h3>${table(r.hotel_relationships||[])}</div></div>`+
 `<div class="grid two" style="margin-top:15px"><div class="card"><h3>Booking History</h3>${table(r.booking_history||[])}</div><div class="card"><h3>Order History</h3>${table(r.order_history||[])}</div></div>`+
 `<div class="card" style="margin-top:15px"><h3>Feedback History</h3>${table(r.feedback_history||[])}</div>`;
}
async function rooms(){
  const status=String(state.roomStatus||"");
  const date=state.roomAvailabilityDate||dateNow();
  const nights=Number(state.roomAvailabilityNights||1);
  const qs=status?`?status=${encodeURIComponent(status)}`:"";
  const [r,a,avail]=await Promise.all([api("/rooms"),api("/room-bookings"+qs),api(`/rooms/availability?check_in_date=${encodeURIComponent(date)}&nights=${nights}`)]);
  const roomActions=`<button data-room-detail="{{i}}">Details</button>`;
  const bookingActions=`<button data-open-booking="{{booking_id}}">View</button> <button data-reservation-edit="{{i}}">Modify</button>`;
  return pageHead("Rooms & Reservations","Room master, availability and complete reservation operations",`<button class="primary" data-action="booking">+ Reservation</button>`)+
   `<div class="toolbar"><select id="room-status-filter"><option value="">All reservation statuses</option>${["Pending","Confirmed","Checked-In","Checked-Out","Cancelled","No-Show"].map(x=>`<option ${status===x?"selected":""}>${x}</option>`).join("")}</select><button id="room-status-clear">Clear</button><input id="room-avail-date" type="date" value="${esc(date)}"><input id="room-avail-nights" type="number" min="1" max="365" value="${nights}"><button id="room-avail-btn">Check Availability</button></div>`+
   `<div class="grid cards">${metric("Rooms",(r.data||[]).length,"Active room master")}${metric("Reservations",(a.data||[]).length,"Reservation records")}${metric("Available",(avail.data||[]).length,`For ${date} • ${nights} night(s)`)}${metric("Occupied",(r.data||[]).filter(x=>x.room_status==="Occupied").length,"Current room status")}</div>`+
   `<div class="grid two"><div class="card"><h3>Room Master</h3>${table(r.data||[],roomActions)}</div><div class="card"><h3>Available Rooms</h3>${table(avail.data||[])}</div></div>`+
   `<div class="card" style="margin-top:15px"><h3>Reservations</h3>${table(a.data||[],bookingActions)}</div>`;
}
async function reservationDetail(bookingId){
 const r=(await api(`/room-bookings/${encodeURIComponent(bookingId)}`));
 const b=r.data||{};
 const action=`${isActionAllowed("room_status")?`<button data-res-action="check-in" data-booking-id="${esc(b.booking_id)}">Check-in</button> <button data-res-action="check-out" data-booking-id="${esc(b.booking_id)}">Check-out</button> <button data-res-action="no-show" data-booking-id="${esc(b.booking_id)}">No-show</button> <button data-res-action="transfer" data-booking-id="${esc(b.booking_id)}">Transfer Room</button> <button data-res-action="stay-options" data-booking-id="${esc(b.booking_id)}">Early/Late</button>`:""}${isActionAllowed("Rooms:Cancel")?` <button data-res-action="cancel" data-booking-id="${esc(b.booking_id)}">Cancel</button>`:""}`;
 return pageHead(`Reservation ${b.booking_id||""}`,`${b.customer_name||"Guest"} • Room ${b.room_number||"—"}`,`<button data-back-rooms>Back</button> <button data-res-action="modify" data-booking-id="${esc(b.booking_id)}">Modify</button>`)+
 `<div class="grid two"><div class="card"><h3>Reservation Details</h3>${table([b])}</div><div class="card"><h3>Room Allocation</h3>${table(r.rooms||[])}</div></div><div class="card" style="margin-top:15px"><h3>Operations</h3>${action||'<span class="section-note">No permitted reservation actions.</span>'}</div>`;
}
async function restaurant(){
  const d=(await api("/restaurant/dashboard")).data||{};
  const o=d.overview||{};
  const orders=d.orders||[], kitchen=d.kitchen_orders||[], menu=d.menu||[], tables=d.tables||[], bookings=d.table_bookings||[];
  const statusOptions=["","New","Preparing","Ready","Served","Completed","Cancelled"];
  const orderRows=orders;
  window.__restaurantOrderRows=orderRows;
  return pageHead("Restaurant / POS Dashboard","Restaurant overview, orders, tables, payments and kitchen operations",`<button class="primary" data-action="order">+ Restaurant Order</button>`)
   +`<div class="grid cards">${metric("Menu Items",o.menu_items,"Configured menu")}${metric("Orders Today",o.orders_today,"Non-cancelled orders")}${metric("Revenue Today",money(o.revenue_today),"Restaurant revenue")}${metric("Pending Payments",money(o.pending_payments),"Outstanding today")}${metric("Available Tables",o.available_tables,"Table status")}${metric("Occupied Tables",o.occupied_tables,"Table status")}</div>`
   +`<div class="card" style="margin-top:15px"><div class="toolbar"><input class="search" id="restaurant-order-search" placeholder="Search order, guest, mobile or table…"><select id="restaurant-order-status">${statusOptions.map(x=>`<option value="${esc(x)}">${x||"All statuses"}</option>`).join("")}</select><button id="restaurant-order-search-btn">Search</button><button id="restaurant-order-clear">Clear</button></div><div id="restaurant-order-results">${table(orderRows,"<button data-restaurant-detail=\"{{i}}\">Details</button>"+(isActionAllowed("order_status")?" <button data-restaurant-status=\"{{i}}\">Update Status</button>":""))}</div></div>`
   +`<div class="grid two" style="margin-top:15px"><div class="card"><h3>Menu Management View</h3>${table(menu)}</div><div class="card"><h3>Kitchen Operational View</h3>${table(kitchen)}</div></div>`
   +`<div class="grid two" style="margin-top:15px"><div class="card"><h3>Table Status</h3>${table(tables)}</div><div class="card"><h3>Table Bookings</h3>${table(bookings)}</div></div>`;
}

async function billing(){
  const [summary,inv]=await Promise.all([api("/billing/summary"),api(`/billing/invoices${state.search?`?search=${encodeURIComponent(state.search)}`:""}`)]);
  const d=summary.data||{}, rows=inv.data||[];
  const actions=`<button data-invoice-detail="{{i}}">Details</button>`;
  return pageHead("Billing & Payments","Invoices, balances, payment status and transaction history",`<button data-refresh>Refresh</button>`)
    +`<div class="grid cards">${metric("Invoices",d.invoice_count||0,"Issued invoices")}${metric("Room Paid",money(d.room?.paid||0),"Room payments")}${metric("Room Balance",money(d.room?.balance||0),"Outstanding")}${metric("Restaurant Paid",money(d.restaurant?.paid||0),"Restaurant payments")}${metric("Restaurant Balance",money(d.restaurant?.balance||0),"Outstanding")}</div>`
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
 return pageHead("Staff & HR","Staff profiles, departments, designations, attendance, leave, salary and payroll")+
 `<div class="grid cards">${metric("Total Staff",summary.total_staff||0,"All staff")}${metric("Active Staff",summary.active_staff||0,"New / Active / On Leave")}${metric("Departments",summary.departments||0,"Active departments")}${metric("Designations",summary.designations||0,"Active designations")}${metric("Pending Leave",summary.pending_leave||0,"Requests")}${metric("Monthly Staff Cost",money(summary.monthly_staff_cost||0),"Current staff salary")}</div>`+
 `<div class="grid three" style="margin-top:15px"><div class="card"><h3>Staff List & Profiles</h3>${table(staffRows)}</div><div class="card"><h3>Departments</h3>${table(departments)}</div><div class="card"><h3>Designations</h3>${table(designationRows)}</div></div>`+
 `<div class="grid three" style="margin-top:15px"><div class="card"><h3>Attendance</h3>${table(attendance)}</div><div class="card"><h3>Leave</h3>${table(leave)}</div><div class="card"><h3>Staff Status</h3>${table(Object.entries(statusCounts).map(([status,count])=>({status,staff_count:count})))}<p class="section-note">Active staff: ${summary.active_staff||0} · Separated: ${summary.separated_staff||0}</p></div></div>`+
 `<div class="grid two" style="margin-top:15px"><div class="card"><h3>Salary</h3>${table(salary)}</div><div class="card"><h3>Payroll</h3>${table(payroll)}</div></div>`+
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
 `<div class="grid three" style="margin-top:15px"><div class="card"><h3>User Activity</h3>${table(rows.map(x=>({username:x.actor_username,role:x.actor_role,module:x.module,action:x.action,timestamp:x.created_at})))}</div><div class="card"><h3>Record References</h3>${table(rows.map(x=>({record_type:x.record_type,record_id:x.record_id,module:x.module,action:x.action})))}</div><div class="card"><h3>Request / Correlation Trace</h3>${table(rows.map(x=>({request_id:x.request_id,username:x.actor_username,action:x.action,timestamp:x.created_at})))}</div></div>`;
}
async function admin(){
 const [h,u,r,p]=await Promise.all([api("/admin/health"),api("/admin/users"),api("/admin/roles"),api("/admin/permissions")]);
 return pageHead("Administration","Database health, users, roles and permission controls",`<button class="primary" data-backup>Backup Database</button>`)
 +`<div class="grid cards">${metric("Database",h.healthy?"Healthy":"Attention","SQLite health")}${metric("Users",(u.data||[]).length,"Hotel users")}${metric("Roles",(r.data||[]).length,"Configured roles")}${metric("Permissions",(p.data||[]).length,"Active permissions")}</div><div class="grid two" style="margin-top:15px"><div class="card"><h3>Users</h3>${table(u.data||[])}</div><div class="card"><h3>Roles</h3>${table(r.data||[])}</div></div>`;
}
async function renderPage(){
 if(!canOpenPage(state.page)){showAccessDenied();return;}
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
 const p=document.getElementById("page");
 p.querySelectorAll("[data-page-prev]").forEach(b=>b.onclick=()=>{const key=b.dataset.pagePrev;state.listPages[key]=Math.max(1,Number(state.listPages[key]||1)-1);render()});
 p.querySelectorAll("[data-page-next]").forEach(b=>b.onclick=()=>{const key=b.dataset.pageNext;state.listPages[key]=Number(state.listPages[key]||1)+1;render()});
 p.querySelectorAll("[data-restaurant-detail]").forEach(b=>b.onclick=()=>{const row=(window.__restaurantOrderRows||[])[Number(b.dataset.restaurantDetail)];if(row)showObjectModal(`Restaurant Order ${row.order_id||""}`,row)});
  p.querySelectorAll("[data-restaurant-status]").forEach(b=>b.onclick=()=>{if(!isActionAllowed("order_status")){showAccessDenied();return;}const row=(window.__restaurantOrderRows||[])[Number(b.dataset.restaurantStatus)];if(!row)return;const statuses=["New","Preparing","Ready","Served","Completed","Cancelled"];formModal("Update Restaurant Order Status",[{name:"status",label:"Status",type:"select",options:statuses,value:row.order_status||"New"}],async o=>api(`/restaurant/orders/${encodeURIComponent(row.order_id)}/status`,{method:"PATCH",body:JSON.stringify(o)}));});
 p.querySelector("#restaurant-order-search-btn")?.addEventListener("click",async()=>{const q=p.querySelector("#restaurant-order-search")?.value.trim();const st=p.querySelector("#restaurant-order-status")?.value||"";try{const qs=new URLSearchParams();if(q)qs.set("search",q);if(st)qs.set("status",st);const r=await api(`/restaurant/orders${qs.toString()?`?${qs}`:""}`);const rows=r.data||[];const actions="<button data-search-order-detail=\"{{i}}\">Details</button>"+(isActionAllowed("order_status")?" <button data-search-order-status=\"{{i}}\">Update Status</button>":"");p.querySelector("#restaurant-order-results").innerHTML=table(rows,actions);p.querySelectorAll("[data-search-order-detail]").forEach(b=>b.onclick=()=>{const row=rows[Number(b.dataset.searchOrderDetail)];if(row)showObjectModal(`Restaurant Order ${row.order_id||""}`,row)});p.querySelectorAll("[data-search-order-status]").forEach(b=>b.onclick=()=>{if(!isActionAllowed("order_status")){showAccessDenied();return;}const row=rows[Number(b.dataset.searchOrderStatus)];if(!row)return;formModal("Update Restaurant Order Status",[{name:"status",label:"Status",type:"select",options:["New","Preparing","Ready","Served","Completed","Cancelled"],value:row.order_status||"New"}],async o=>api(`/restaurant/orders/${encodeURIComponent(row.order_id)}/status`,{method:"PATCH",body:JSON.stringify(o)}));});}catch(e){toast(e.message,true)}});
 p.querySelector("#restaurant-order-clear")?.addEventListener("click",()=>{p.querySelector("#restaurant-order-search").value="";p.querySelector("#restaurant-order-status").value="";p.querySelector("#restaurant-order-search-btn")?.click()});

 p.querySelector("[data-feedback-filter]")?.addEventListener("click",()=>{state.feedbackSearch=p.querySelector("#feedback-search")?.value.trim()||"";state.feedbackCategory=p.querySelector("#feedback-category")?.value||"";state.feedbackRating=p.querySelector("#feedback-rating")?.value||"";state.feedbackStatus=p.querySelector("#feedback-status")?.value||"";state.feedbackComplaints=p.querySelector("#feedback-complaints")?.value||"";state.feedbackFollow=p.querySelector("#feedback-follow")?.value||"";render()});
 p.querySelector("[data-feedback-clear]")?.addEventListener("click",()=>{state.feedbackSearch=state.feedbackCategory=state.feedbackRating=state.feedbackStatus=state.feedbackComplaints=state.feedbackFollow="";render()});
 p.querySelectorAll("[data-feedback-manage],[data-complaint-manage]").forEach(b=>b.onclick=()=>{if(!isActionAllowed("feedback_update")){showAccessDenied();return;}const isComplaint=b.dataset.complaintManage!==undefined;const row=(isComplaint?window.__complaintRows:window.__feedbackRows||[])[Number(isComplaint?b.dataset.complaintManage:b.dataset.feedbackManage)];if(!row)return;formModal(`Manage Feedback ${row.feedback_id}`,[{name:"rating",label:"Rating",type:"number",value:row.rating||5},{name:"review",label:"Review",value:row.feedback||"",full:true},{name:"category",label:"Category",type:"select",options:["General","Room","Restaurant","Cleanliness","Staff","Service","Facilities","Billing","Other"],value:row.category||"General"},{name:"complaint",label:"Complaint",required:false,value:row.complaint||"",full:true},{name:"issue",label:"Issue",required:false,value:row.issue||"",full:true},{name:"resolution",label:"Resolution",required:false,value:row.resolution||"",full:true},{name:"status",label:"Status",type:"select",options:["Open","In Progress","Resolved","Closed"],value:row.status||"Closed"},{name:"follow_up_required",label:"Follow-up Required",type:"select",options:["false","true"],value:Number(row.follow_up_required||0)?"true":"false"},{name:"follow_up_date",label:"Follow-up Date (DD-MM-YYYY)",required:false,value:row.follow_up_date||""},{name:"follow_up_method",label:"Follow-up Method",type:"select",options:["","Call","WhatsApp","Email"],required:false,value:row.follow_up_method||""},{name:"follow_up_status",label:"Follow-up Status",type:"select",options:["","Pending","Completed"],required:false,value:row.follow_up_status||""},{name:"follow_up_notes",label:"Follow-up Notes",required:false,value:row.follow_up_notes||"",full:true}],o=>api(`/feedback/${encodeURIComponent(row.feedback_id)}`,{method:"PATCH",body:JSON.stringify({...o,rating:Number(o.rating),follow_up_required:String(o.follow_up_required).toLowerCase()==="true",allow_pending_complaint:true})}));});

 p.querySelector("[data-notification-filter]")?.addEventListener("click",()=>render());
 p.querySelector("[data-notification-clear]")?.addEventListener("click",()=>{state.page="notifications";render()});
 p.querySelector("#notification-search")?.addEventListener("keydown",e=>{if(e.key==="Enter")render()});
 p.querySelector("#inventory-search-btn")?.addEventListener("click",()=>{state.inventorySearch=p.querySelector("#inventory-search")?.value.trim()||"";render()});
 p.querySelector("#inventory-clear")?.addEventListener("click",()=>{state.inventorySearch="";render()});
 p.querySelectorAll("[data-inv-stock]").forEach(b=>b.onclick=()=>{if(!isActionAllowed("inventory_stock")){showAccessDenied();return;}const row=(window.__inventoryItems||[])[Number(b.dataset.invStock)];if(!row)return;formModal(`Stock Movement - ${row.item_id}`,[{name:"movement",label:"Movement",type:"select",options:["Stock In","Stock Out","Adjustment Increase","Adjustment Decrease","Damaged"]},{name:"quantity",label:"Quantity",type:"number",placeholder:"Required"},{name:"reason",label:"Reason"},{name:"reference_no",label:"Reference No"}],async o=>{const qty=Number(o.quantity||0);if(qty<=0)throw new Error("Quantity must be greater than zero.");let path="/inventory/stock-in",body={item_id:row.item_id,quantity:qty,reason:o.reason,reference_no:o.reference_no};if(o.movement==="Stock Out")path="/inventory/stock-out";else if(o.movement==="Adjustment Increase"||o.movement==="Adjustment Decrease"){path="/inventory/adjustment";body={item_id:row.item_id,adjustment_type:o.movement.endsWith("Increase")?"INCREASE":"DECREASE",quantity:qty,reason:o.reason,reference_no:o.reference_no};}else if(o.movement==="Damaged")path="/inventory/damaged";await api(path,{method:"POST",body:JSON.stringify(body)});toast("Inventory movement saved.");render()});});
 p.querySelectorAll("[data-action]").forEach(b=>{if(!isActionAllowed(b.dataset.action)){b.remove();return;}b.onclick=()=>openAction(b.dataset.action)});
 p.querySelector("[data-refresh]")?.addEventListener("click",render);
 p.querySelector("[data-backup]")?.addEventListener("click",async()=>{if(!isActionAllowed("backup")){showAccessDenied();return;}try{const r=await api("/admin/backup",{method:"POST"});toast("Backup created.");console.log(r)}catch(e){toast(e.message,true)}});
 p.querySelector("#do-search")?.addEventListener("click",()=>{const q=p.querySelector("#page-search").value.trim();state.search=q;render()}); p.querySelector("#billing-search-btn")?.addEventListener("click",()=>{state.search=p.querySelector("#billing-search")?.value.trim()||"";render()});
 p.querySelector("#billing-clear")?.addEventListener("click",()=>{state.search="";render()});
 p.querySelectorAll("[data-invoice-detail]").forEach(b=>b.onclick=async()=>{const rows=(await api(`/billing/invoices${state.search?`?search=${encodeURIComponent(state.search)}`:""}`)).data||[];const row=rows[Number(b.dataset.invoiceDetail)];if(!row)return;try{const d=(await api(`/billing/invoices/${encodeURIComponent(row.invoice_number)}`)).data;showObjectModal("Invoice Details",d)}catch(e){toast(e.message,true)}});

 p.querySelector("#clear-search")?.addEventListener("click",()=>{state.search="";render()});
 p.querySelector("#guest-search-btn")?.addEventListener("click",()=>{state.guestSearch=p.querySelector("#guest-search")?.value||"";state.guestSearchField=p.querySelector("#guest-search-field")?.value||"all";state.guestStatus=p.querySelector("#guest-status-filter")?.value||"";render()});
 p.querySelector("#guest-clear-btn")?.addEventListener("click",()=>{state.guestSearch="";state.guestSearchField="all";state.guestStatus="";render()});
 p.querySelectorAll("[data-guest-detail]").forEach(b=>b.onclick=async()=>{const rows=(await api("/customers?search_field="+(state.guestSearchField||"all")+(state.guestSearch?"&search="+encodeURIComponent(state.guestSearch):"")+(state.guestStatus?"&guest_status="+encodeURIComponent(state.guestStatus):""))).data||[];const row=rows[Number(b.dataset.guestDetail)];if(!row)return;try{document.getElementById("page").innerHTML=`<div class="loading">Loading guest…</div>`;document.getElementById("page").innerHTML=await guestDetail(row.customer_id);bindPageEvents()}catch(e){document.getElementById("page").innerHTML=`<div class="error-box">${esc(e.message)}</div>`}});
 p.querySelectorAll("[data-guest-edit]").forEach(b=>b.onclick=async()=>{const rows=(await api("/customers?search_field="+(state.guestSearchField||"all")+(state.guestSearch?"&search="+encodeURIComponent(state.guestSearch):"")+(state.guestStatus?"&guest_status="+encodeURIComponent(state.guestStatus):""))).data||[];const row=rows[Number(b.dataset.guestEdit)];if(row)openGuestEdit(row)});
 p.querySelector("[data-back-guests]")?.addEventListener("click",()=>render());
 p.querySelector("[data-edit-current]")?.addEventListener("click",async e=>{const r=(await api(`/customers/${encodeURIComponent(e.currentTarget.dataset.editCurrent)}`)).data;openGuestEdit(r.customer)});
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
 p.querySelectorAll("[data-room-detail]").forEach(b=>b.onclick=async()=>{const rows=(await api("/rooms")).data||[];const row=rows[Number(b.dataset.roomDetail)];if(row)showObjectModal("Room Details",row)});
 p.querySelectorAll("[data-reservation-detail]").forEach(b=>b.onclick=async()=>{const rows=(await api("/room-bookings")).data||[];const row=rows[Number(b.dataset.reservationDetail)];if(!row)return;state.page="rooms";document.getElementById("page").innerHTML=`<div class="loading">Loading reservation…</div>`;document.getElementById("page").innerHTML=await reservationDetail(row.booking_id);bindPageEvents()});
 p.querySelectorAll("[data-reservation-edit]").forEach(b=>b.onclick=async()=>{const rows=(await api("/room-bookings")).data||[];const row=rows[Number(b.dataset.reservationEdit)];if(row)openReservationEdit(row)});
 p.querySelector("#room-status-filter")?.addEventListener("change",e=>{state.roomStatus=e.target.value;render()});
 p.querySelector("#room-status-clear")?.addEventListener("click",()=>{state.roomStatus="";render()});
 p.querySelector("#room-avail-btn")?.addEventListener("click",()=>{state.roomAvailabilityDate=p.querySelector("#room-avail-date").value||dateNow();state.roomAvailabilityNights=Number(p.querySelector("#room-avail-nights").value||1);render()});
 p.querySelector("[data-back-rooms]")?.addEventListener("click",()=>render());
 p.querySelectorAll("[data-res-action]").forEach(b=>b.onclick=()=>reservationAction(b.dataset.resAction,b.dataset.bookingId));
 p.querySelectorAll("[data-page]").forEach(b=>b.onclick=()=>{state.page=b.dataset.page;render()});
 p.querySelectorAll("[data-open-booking]").forEach(b=>b.onclick=async()=>{try{state.page="frontdesk";document.getElementById("page").innerHTML=`<div class="loading">Loading reservation…</div>`;document.getElementById("page").innerHTML=await reservationDetail(b.dataset.openBooking);bindPageEvents()}catch(e){toast(e.message,true)}});
 p.querySelectorAll("[data-front-action]").forEach(b=>b.onclick=async()=>{if(!isActionAllowed("room_status")){showAccessDenied();return;}try{const action=b.dataset.frontAction,id=encodeURIComponent(b.dataset.bookingId||"");if(!id){toast("Reservation not found.",true);return;}const endpoint=action==="check-in"?`/room-bookings/${id}/check-in`:`/room-bookings/${id}/check-out`;await api(endpoint,{method:"POST",body:"{}"});toast(action==="check-in"?"Guest checked in.":"Guest checked out.");render()}catch(e){toast(e.message,true)}});
 p.querySelector("#frontdesk-lookup-btn")?.addEventListener("click",async()=>{const q=p.querySelector("#frontdesk-lookup")?.value.trim();const target=p.querySelector("#frontdesk-lookup-results");if(!q){target.innerHTML=`<div class="empty-state">Enter a guest name, mobile or customer ID.</div>`;return;}try{target.innerHTML=`<div class="loading">Searching…</div>`;const r=await api(`/frontdesk/guest-lookup?q=${encodeURIComponent(q)}`);target.innerHTML=(r.data||[]).length?table(r.data||[],row=>`<button data-open-booking="${esc(row.booking_id||"")}">View</button>`):`<div class="empty-state">No matching guest records found.</div>`;target.querySelectorAll("[data-open-booking]").forEach(b=>b.onclick=async()=>{document.getElementById("page").innerHTML=`<div class="loading">Loading reservation…</div>`;document.getElementById("page").innerHTML=await reservationDetail(b.dataset.openBooking);bindPageEvents()})}catch(e){target.innerHTML=`<div class="error-box">${esc(e.message)}</div>`}});
 p.querySelector("#frontdesk-res-search-btn")?.addEventListener("click",async()=>{const q=p.querySelector("#frontdesk-res-search")?.value.trim();const target=p.querySelector("#frontdesk-res-results");if(!q){target.innerHTML=table((d.reservation_results||[]),rowActions);return;}try{const r=await api(`/frontdesk?search=${encodeURIComponent(q)}`);const data=r.data||{};target.innerHTML=(data.reservation_results||[]).length?table(data.reservation_results||[],rowActions):`<div class="empty-state">No matching reservations found.</div>`;bindPageEvents()}catch(e){target.innerHTML=`<div class="error-box">${esc(e.message)}</div>`}});
 p.querySelector("#frontdesk-res-clear")?.addEventListener("click",()=>render());
}
function openReservationEdit(b){
 if(!isActionAllowed("room_status")){showAccessDenied();return;}
 return formModal("Modify Reservation",[
  {name:"customer_name",label:"Guest name",required:false,value:b.customer_name||""},{name:"customer_mobile",label:"Mobile",required:false,value:b.customer_mobile||""},{name:"room_number",label:"Room number(s)",required:false,value:b.room_number||""},{name:"check_in_date",label:"Check-in date",type:"date",required:false,value:toInputDate(b.check_in_date)},{name:"nights",label:"Nights",type:"number",required:false,value:b.nights||b.days||1},{name:"adults",label:"Adults",type:"number",required:false,value:b.adults||1},{name:"children",label:"Children",type:"number",required:false,value:b.children||0},{name:"notes",label:"Special requests",required:false,value:b.notes||"",full:true}
 ],o=>api(`/room-bookings/${encodeURIComponent(b.booking_id)}`,{method:"PATCH",body:JSON.stringify(o)}));
}
function toInputDate(v){if(!v)return "";const m=String(v).match(/^(\d{2})-(\d{2})-(\d{4})$/);return m?`${m[3]}-${m[2]}-${m[1]}`:String(v).slice(0,10)}
async function reservationAction(action,bookingId){
 try{
  if(action==="modify"){const r=await api(`/room-bookings/${encodeURIComponent(bookingId)}`);return openReservationEdit(r.data)}
  if(action==="cancel")return formModal("Cancel Reservation",[{name:"reason",label:"Cancellation reason"}],o=>api(`/room-bookings/${encodeURIComponent(bookingId)}/cancel`,{method:"POST",body:JSON.stringify(o)}));
  if(action==="no-show")return formModal("No-Show Reservation",[{name:"reason",label:"No-show reason"}],o=>api(`/room-bookings/${encodeURIComponent(bookingId)}/no-show`,{method:"POST",body:JSON.stringify(o)}));
  if(action==="transfer")return formModal("Transfer Room",[{name:"new_room_number",label:"New room number"}],o=>api(`/room-bookings/${encodeURIComponent(bookingId)}/transfer`,{method:"POST",body:JSON.stringify(o)}));
  if(action==="stay-options")return formModal("Early / Late Stay Options",[{name:"early_check_in_time",label:"Early check-in time",required:false},{name:"late_check_out_time",label:"Late check-out time",required:false}],o=>api(`/room-bookings/${encodeURIComponent(bookingId)}/stay-options`,{method:"PATCH",body:JSON.stringify(o)}));
  const endpoint={"check-in":"check-in","check-out":"check-out"}[action];
  if(endpoint)return api(`/room-bookings/${encodeURIComponent(bookingId)}/${endpoint}`,{method:"POST",body:"{}"});
 }catch(e){toast(e.message,true)}
}

async function statusAction(type,index){
 try{
  const path=type==="room"?"/room-bookings":"/restaurant/orders";const r=await api(path);const row=r.data?.[Number(index)];if(!row)return;
  const id=type==="room"?row.booking_id:row.order_id;const choices=type==="room"?["Pending","Confirmed","Checked-In","Checked-Out","Cancelled","No-Show"]:["Pending","Preparing","Ready","Served","Completed","Cancelled"];
  formModal("Update Status",[{name:"status",label:"Status",type:"select",options:choices}],async o=>api(`${type==="room"?"/room-bookings/":"/restaurant/orders/"}${encodeURIComponent(id)}/status`,{method:"PATCH",body:JSON.stringify(o)}));
 }catch(e){toast(e.message,true)}
}
function openGuestEdit(c){
 if(!isActionAllowed("guest_update")){showAccessDenied();return;}
 return formModal("Edit Guest",[
  {name:"customer_name",label:"Guest name",value:c.customer_name||""},{name:"customer_mobile",label:"Mobile",value:c.customer_mobile||""},{name:"customer_email",label:"Email",required:false,value:c.customer_email||""},{name:"customer_address",label:"Address",required:false,value:c.customer_address||""},{name:"customer_city",label:"City",required:false,value:c.customer_city||""},{name:"customer_state",label:"State",required:false,value:c.customer_state||""},{name:"customer_country",label:"Country",required:false,value:c.customer_country||"India"},{name:"customer_pincode",label:"Pincode",required:false,value:c.customer_pincode||""},{name:"guest_status",label:"Status",type:"select",options:["Active","Inactive","Blacklisted"],value:c.guest_status||"Active"},{name:"preferences",label:"Preferences",required:false,value:c.preferences||"",full:true},{name:"special_requests",label:"Special requests",required:false,value:c.special_requests||"",full:true},{name:"guest_notes",label:"Guest notes",required:false,value:c.guest_notes||"",full:true}
 ],o=>api(`/customers/${encodeURIComponent(c.customer_id)}`,{method:"PUT",body:JSON.stringify({...o,is_active:o.guest_status!=="Inactive"})}));
}
function openAction(a){
 if(a==="customer")return formModal("New Guest",[
  {name:"customer_name",label:"Guest name"},{name:"customer_mobile",label:"Mobile"},{name:"customer_email",label:"Email",required:false},{name:"customer_city",label:"City",required:false},{name:"customer_state",label:"State",required:false},{name:"customer_country",label:"Country",required:false},{name:"customer_pincode",label:"Pincode",required:false},{name:"preferences",label:"Preferences",required:false,full:true},{name:"special_requests",label:"Special requests",required:false,full:true},{name:"guest_notes",label:"Notes",required:false,full:true}
 ],o=>api("/customers",{method:"POST",body:JSON.stringify(o)}));
 if(a==="booking")return formModal("New Room Reservation",[
  {name:"customer_name",label:"Guest name"},{name:"customer_mobile",label:"Mobile"},{name:"customer_id",label:"Customer ID",required:false},{name:"room_number",label:"Room number"},{name:"days",label:"Nights",type:"number"},{name:"check_in_date",label:"Check-in date",type:"date",required:false},{name:"advance_amount",label:"Advance",type:"number",required:false},{name:"payment_method",label:"Payment method",required:false},{name:"adults",label:"Adults",type:"number",required:false},{name:"children",label:"Children",type:"number",required:false},{name:"notes",label:"Special requests",required:false,full:true}
 ],o=>api("/room-bookings",{method:"POST",body:JSON.stringify(o)}));
 if(a==="order")return formModal("Restaurant Order",[
  {name:"customer_name",label:"Guest name"},{name:"customer_mobile",label:"Mobile"},{name:"table_number",label:"Table"},{name:"customer_id",label:"Customer ID",required:false},{name:"items",label:"Items JSON",placeholder:'[{"item_id":"ITEM-01","quantity":2}]',full:true},{name:"discount",label:"Discount",type:"number",required:false},{name:"payment_method",label:"Payment method",required:false},{name:"paid_amount",label:"Paid amount",type:"number",required:false},{name:"advance_amount",label:"Advance",type:"number",required:false},{name:"order_notes",label:"Notes",required:false,full:true}
 ],async o=>{try{o.items=JSON.parse(o.items)}catch{throw new Error("Items JSON is invalid.")}return api("/restaurant/orders",{method:"POST",body:JSON.stringify(o)})});
 if(a==="expense")return formModal("New Expense",[
  {name:"expense_id",label:"Expense ID"},{name:"expense_date",label:"Date",type:"date"},{name:"expense_time",label:"Time",placeholder:"HH:MM"},{name:"expense_name",label:"Expense name"},{name:"amount",label:"Amount",type:"number"},{name:"category",label:"Category"},{name:"category_id",label:"Category ID",required:false},{name:"vendor_id",label:"Vendor / Supplier ID",required:false},{name:"payment_method",label:"Payment method",type:"select",options:["Cash","Card","UPI","Online","Bank Transfer","Cheque","Other"]},{name:"receipt_reference",label:"Receipt / Reference",required:false},{name:"department_id",label:"Department ID",required:false},{name:"description",label:"Description"},{name:"is_recurring",label:"Recurring",type:"select",options:["false","true"],value:"false"},{name:"recurrence_frequency",label:"Recurrence frequency",type:"select",options:["","Daily","Weekly","Monthly","Quarterly","Yearly"],required:false},{name:"recurrence_start_date",label:"Recurrence start date",type:"date",required:false}
 ],o=>api("/expenses",{method:"POST",body:JSON.stringify({...o,amount:Number(o.amount),is_recurring:String(o.is_recurring).toLowerCase()==="true",recurrence_frequency:o.recurrence_frequency||undefined,recurrence_start_date:o.recurrence_start_date||undefined})}));
 if(a==="transport")return formModal("Transportation Request",[
  {name:"customer_id",label:"Customer ID",required:false},{name:"guest_name",label:"Guest name",required:false},{name:"guest_mobile",label:"Mobile",required:false},{name:"transportation_type",label:"Type",type:"select",options:["Airport Pickup","Airport Drop","Railway Station Pickup","Railway Station Drop","Local Transportation","Taxi / Cab Request"]},
  {name:"pickup_date",label:"Pickup date",type:"date"},{name:"pickup_time",label:"Pickup time"},{name:"pickup_location",label:"Pickup location"},{name:"drop_location",label:"Drop location"},{name:"vehicle_type",label:"Vehicle type",required:false},{name:"fare",label:"Fare",type:"number",required:false},{name:"special_request",label:"Special request",required:false,full:true},{name:"notes",label:"Notes",required:false,full:true}
 ],o=>api("/transportation/requests",{method:"POST",body:JSON.stringify(o)}));
}
async function render(){setTop();setActive();refreshNotificationBadge();await renderPage();setActive();setTop()}
function connectionBanner(){
  let b=document.getElementById("connection-banner");
  if(!b){b=document.createElement("div");b.id="connection-banner";b.className="connection-banner hidden";b.textContent="Offline — reconnecting…";document.body.appendChild(b);}
  b.classList.toggle("hidden", navigator.onLine);
}
window.addEventListener("online", connectionBanner);
window.addEventListener("offline", connectionBanner);

async function boot(){
 buildNav();
 document.getElementById("login-form").onsubmit=async e=>{e.preventDefault();const err=document.getElementById("login-error");err.textContent="";try{const payload={username:document.getElementById("login-username").value.trim(),password:document.getElementById("login-password").value};const h=document.getElementById("login-hotel").value;if(h)payload.hotel_id=Number(h);const r=await api("/auth/login",{method:"POST",body:JSON.stringify(payload)});persistAuth(r.access_token,r.user,r.expires_in);state.hotelContext=(await api("/hotel/context")).data||null;const perm=await api("/auth/permissions");state.user.permissions=perm.data||[];showDashboard();await render()}catch(e){err.textContent=e.message}};
 document.getElementById("logout-btn").onclick=()=>forceLogout("");
 document.getElementById("user-btn").onclick=()=>openUserProfile();
 document.getElementById("notification-btn").onclick=()=>{if(!canOpenPage("notifications")){showAccessDenied();return;}state.page="notifications";closeSidebar();render()};
 document.getElementById("refresh-btn").onclick=render;
 document.getElementById("menu-toggle").onclick=()=>document.getElementById("sidebar").classList.contains("open")?closeSidebar():openSidebar();
 document.getElementById("sidebar-close").onclick=closeSidebar;
 document.getElementById("sidebar-overlay").onclick=closeSidebar;
 window.addEventListener("resize",()=>{if(window.innerWidth>800)closeSidebar()});
 if(state.token && !storedTokenIsExpired()){restoreAuthTimer();try{state.user=(await api("/auth/me")).data;const perm=await api("/auth/permissions");state.user.permissions=perm.data||[];showDashboard();state.hotelContext=(await api("/hotel/context")).data||null;await render()}catch{forceLogout("")}}else{clearAuth();showLogin("");}
  bindExpenseEvents();
}
boot();

window.addEventListener("error", () => toast("Unexpected dashboard error. Please refresh the page.", true));
window.addEventListener("unhandledrejection", () => toast("A dashboard operation failed. Please try again.", true));
