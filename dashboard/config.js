// Runtime dashboard configuration. Same-origin is the safe default.
// A deployment may set window.YH_API_BASE before app.js loads.
window.YH_DASHBOARD_CONFIG = Object.freeze({
  apiBase: window.YH_API_BASE || "/api/v1",
  appName: "YADAV HOTEL Admin Dashboard",
  requestTimeoutMs: 15000,
});
