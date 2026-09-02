const ADMIN_NAV_ITEMS = [
  { href: "admin-dashboard.html", label: "Tableau de bord", key: "admin-dashboard", show: () => true },
  { href: "admin-boutiques.html", label: "Boutiques", key: "admin-boutiques", show: () => true },
  { href: "admin-tickets.html", label: "Support", key: "admin-tickets", show: () => true },
  { href: "admin-utilisateurs.html", label: "Utilisateurs", key: "admin-utilisateurs", show: () => true },
  { href: "admin-journal.html", label: "Journal", key: "admin-journal", show: () => true },
  { href: "admin-parametres.html", label: "Paramètres", key: "admin-parametres", show: (u) => u.admin_role === "super" },
];

function renderAdminLayout(activeKey, pageTitle, pageSub) {
  document.body.insertAdjacentHTML("afterbegin", `
    <div class="mobile-topbar">
      <button id="menuToggle" aria-label="Menu">&#9776;</button>
      <span>MobiBiz Admin</span>
    </div>
    <div class="sidebar-backdrop" id="sidebarBackdrop"></div>
    <div class="app">
      <aside class="sidebar" id="sidebar">
        <div class="sidebar__brand">MobiBiz<span class="dot">.</span></div>
        <div class="sidebar__shop">Administration</div>
        <nav id="sidebarNav"></nav>
        <div class="sidebar__footer">
          <a href="mon-compte.html" style="display:block;padding:10px 0;color:#c7c9d8;font-size:14.5px">Mon compte</a>
          <button id="logoutBtn">Déconnexion</button>
        </div>
      </aside>
      <main class="main">
        <div class="topbar">
          <div>
            <h1>${pageTitle}</h1>
            ${pageSub ? `<p class="sub">${pageSub}</p>` : ""}
          </div>
          <div class="topbar-actions" id="topbarActions" style="display:flex;align-items:center;gap:10px">
            <div id="adminNotifBell" style="position:relative;cursor:pointer">
              <span style="font-size:20px">🔔</span>
              <span id="adminNotifBadge" class="badge red" style="display:none;position:absolute;top:-6px;right:-10px;min-width:18px;text-align:center;padding:1px 5px"></span>
              <div id="adminNotifDropdown" class="card hidden" style="position:absolute;right:0;top:30px;width:300px;z-index:60;margin:0;font-size:13.5px"></div>
            </div>
          </div>
        </div>
        <div id="pageContent"></div>
      </main>
    </div>
  `);

  document.getElementById("logoutBtn").addEventListener("click", () => {
    Auth.clear();
    window.location.href = "index.html";
  });

  const sidebar = document.getElementById("sidebar");
  const backdrop = document.getElementById("sidebarBackdrop");
  document.getElementById("menuToggle").addEventListener("click", () => {
    sidebar.classList.toggle("open");
    backdrop.classList.toggle("open");
  });
  backdrop.addEventListener("click", () => {
    sidebar.classList.remove("open");
    backdrop.classList.remove("open");
  });

  api("/api/auth/me").then((user) => {
    if (user.role !== "admin") {
      window.location.href = "dashboard.html";
      return;
    }
    const navHtml = ADMIN_NAV_ITEMS.filter((item) => item.show(user)).map(
      (item) => `<a href="${item.href}" class="${item.key === activeKey ? "active" : ""}">${item.label}</a>`
    ).join("");
    document.getElementById("sidebarNav").innerHTML = navHtml;
    initAdminNotifBell();
  }).catch(() => {});
}

function initAdminNotifBell() {
  const bell = document.getElementById("adminNotifBell");
  const badge = document.getElementById("adminNotifBadge");
  const dropdown = document.getElementById("adminNotifDropdown");

  async function refresh() {
    try {
      const n = await api("/api/admin/notifications");
      const total = n.tickets_ouverts + n.paiements_en_retard + n.essais_expirant_bientot;
      if (total > 0) {
        badge.textContent = total > 9 ? "9+" : total;
        badge.style.display = "block";
      } else {
        badge.style.display = "none";
      }
      dropdown.innerHTML = `
        <div style="padding:8px 4px;border-bottom:1px solid var(--border)">🎫 Tickets ouverts : <strong>${n.tickets_ouverts}</strong></div>
        <div style="padding:8px 4px;border-bottom:1px solid var(--border)">💸 Paiements en retard : <strong>${n.paiements_en_retard}</strong></div>
        <div style="padding:8px 4px;border-bottom:1px solid var(--border)">⏳ Essais expirant sous 3j : <strong>${n.essais_expirant_bientot}</strong></div>
        <div style="padding:8px 4px">🆕 Nouvelles boutiques (7j) : <strong>${n.nouvelles_boutiques_7j}</strong></div>
      `;
    } catch (_) { /* ignore */ }
  }

  bell.addEventListener("click", (e) => { e.stopPropagation(); dropdown.classList.toggle("hidden"); });
  document.addEventListener("click", () => dropdown.classList.add("hidden"));

  refresh();
  setInterval(refresh, 30000);
}
