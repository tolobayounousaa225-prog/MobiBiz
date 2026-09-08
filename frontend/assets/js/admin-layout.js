const ADMIN_NAV_ITEMS = [
  { href: "admin-dashboard.html", label: "Tableau de bord", key: "admin-dashboard", icon: "◧", show: () => true },
  { href: "admin-boutiques.html", label: "Boutiques", key: "admin-boutiques", icon: "◫", show: () => true },
  { href: "admin-tickets.html", label: "Support", key: "admin-tickets", icon: "?", badgeKey: "tickets_ouverts", show: () => true },
  { href: "admin-utilisateurs.html", label: "Utilisateurs", key: "admin-utilisateurs", icon: "◎", show: () => true },
  { href: "admin-journal.html", label: "Journal", key: "admin-journal", icon: "▤", show: () => true },
  { href: "admin-parametres.html", label: "Paramètres", key: "admin-parametres", icon: "⚙", show: (u) => u.admin_role === "super" },
];

const ADMIN_ROLE_LABELS = { super: "Super admin", support: "Support" };

function renderAdminLayout(activeKey, pageTitle, pageSub) {
  document.body.classList.add("admin-app");
  document.body.insertAdjacentHTML("afterbegin", `
    <div class="mobile-topbar">
      <button id="menuToggle" aria-label="Menu">&#9776;</button>
      <span>MobiBiz Admin</span>
    </div>
    <div class="sidebar-backdrop" id="sidebarBackdrop"></div>
    <div class="app">
      <aside class="sidebar" id="sidebar">
        <div class="sidebar__brand">MobiBiz<span class="dot">.</span></div>
        <div class="brand-sub">Administration</div>
        <div class="admin-chip" id="adminChip"></div>
        <nav id="sidebarNav" class="nav"></nav>
        <div class="sidebar__footer">
          <a href="mon-compte.html" class="${activeKey === "mon-compte" ? "active" : ""}">Mon compte</a>
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
            <div id="adminNotifBell" class="bell">
              🔔
              <span id="adminNotifBadge" class="dot" style="display:none"></span>
              <div id="adminNotifDropdown" class="card hidden" style="position:absolute;right:0;top:44px;width:300px;z-index:60;margin:0;font-size:13.5px"></div>
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
    const initials = `${(user.prenom || "?")[0]}${(user.nom || "?")[0]}`.toUpperCase();
    const roleLabel = ADMIN_ROLE_LABELS[user.admin_role] || user.admin_role || "Admin";
    document.getElementById("adminChip").innerHTML = `
      <div class="avatar">${escapeHtml(initials)}</div>
      <div><div class="name">${escapeHtml(user.prenom)} ${escapeHtml(user.nom)}</div><div class="role">${escapeHtml(roleLabel)}</div></div>
    `;
    const navHtml = ADMIN_NAV_ITEMS.filter((item) => item.show(user)).map(
      (item) => `<a href="${item.href}" class="${item.key === activeKey ? "active" : ""}"><span class="ic">${item.icon}</span> ${item.label}${
        item.badgeKey ? `<span class="nav-count hidden" data-admin-nav-badge="${item.badgeKey}"></span>` : ""
      }</a>`
    ).join("");
    document.getElementById("sidebarNav").innerHTML = navHtml;
    initAdminNotifBell();
  }).catch(() => {});
}

function initAdminNotifBell() {
  const bell = document.getElementById("adminNotifBell");
  const badge = document.getElementById("adminNotifBadge");
  const dropdown = document.getElementById("adminNotifDropdown");
  const navBadges = document.querySelectorAll("[data-admin-nav-badge]");

  async function refresh() {
    try {
      const n = await api("/api/admin/notifications");
      const total = n.tickets_ouverts + n.paiements_en_retard + n.essais_expirant_bientot;
      if (total > 0) {
        badge.textContent = total > 9 ? "9+" : total;
        badge.style.display = "flex";
      } else {
        badge.style.display = "none";
      }
      navBadges.forEach((el) => {
        const count = n[el.dataset.adminNavBadge] || 0;
        if (count > 0) {
          el.textContent = count > 9 ? "9+" : count;
          el.classList.remove("hidden");
        } else {
          el.classList.add("hidden");
        }
      });
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
