(() => {
  const $ = selector => document.querySelector(selector);
  const tokenKey = "oe-admin-token";
  const money = value => new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(value);
  const esc = value => String(value ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const currentHour = new Date().getHours();
  $("#dayTime").textContent = currentHour < 12 ? "morning" : currentHour < 17 ? "afternoon" : "evening";

  async function request(url, options = {}) {
    const token = sessionStorage.getItem(tokenKey);
    const response = await fetch(url, { ...options, headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) } });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || data.msg || "Request failed");
    return data;
  }

  async function loadDashboard() {
    try {
      const data = await request("/api/admin/stats");
      $("#loginView").classList.add("hidden"); $("#dashboard").classList.remove("hidden");
      $("#leadCount").textContent = data.leads; $("#quoteCount").textContent = data.quotations;
      $("#revenueCount").textContent = money(data.revenue); $("#categoryCount").textContent = data.categories;
      $("#leadsTable").innerHTML = data.recent_leads.length ? data.recent_leads.map(row => `<tr><td><b>${esc(row.name)}</b>${esc(row.phone)}</td><td>${esc(row.request_type)}</td><td>${esc(row.event_date || "To discuss")}</td><td><span class="status">${esc(row.status)}</span></td></tr>`).join("") : '<tr><td colspan="4">No inquiries yet.</td></tr>';
      $("#quotesList").innerHTML = data.recent_quotes.length ? data.recent_quotes.map(row => `<div class="quote-row"><div><b>${esc(row.customer)}</b><small>${esc(row.event_date)} · ${esc(row.public_id.toUpperCase())}</small></div><strong>${money(row.grand_total)}</strong></div>`).join("") : "<p>No quotations yet.</p>";
    } catch { sessionStorage.removeItem(tokenKey); $("#loginView").classList.remove("hidden"); $("#dashboard").classList.add("hidden"); }
  }

  $("#loginForm").addEventListener("submit", async event => {
    event.preventDefault(); $("#loginError").textContent = "";
    try {
      const payload = Object.fromEntries(new FormData(event.currentTarget));
      const data = await request("/api/auth/login", { method: "POST", body: JSON.stringify(payload) });
      sessionStorage.setItem(tokenKey, data.access_token); loadDashboard();
    } catch (error) { $("#loginError").textContent = error.message; }
  });
  $("#logoutButton").addEventListener("click", () => { sessionStorage.removeItem(tokenKey); location.reload(); });
  if (sessionStorage.getItem(tokenKey)) loadDashboard();
})();
