const EMPLOYEE_MODULE_ACCESS = {
  manager: ["produits", "commandes", "stock"],
  vendeur: ["commandes"],
  magasinier: ["stock"],
  comptable: ["finance"],
};

function hasAccess(user, module) {
  if (!user) return false;
  if (user.role === "owner") return true;
  if (user.role === "employee" && user.employee_role) {
    return (EMPLOYEE_MODULE_ACCESS[user.employee_role] || []).includes(module);
  }
  return false;
}

const NAV_ITEMS = [
  { href: "dashboard.html", label: "Tableau de bord", key: "dashboard", show: () => true },
  { href: "produits.html", label: "Produits", key: "produits", show: (u) => hasAccess(u, "produits") },
  { href: "stock.html", label: "Stock", key: "stock", show: (u) => hasAccess(u, "stock") },
  { href: "clients.html", label: "Clients", key: "clients", show: () => true },
  { href: "commandes.html", label: "Commandes", key: "commandes", show: (u) => hasAccess(u, "commandes") },
  { href: "finances.html", label: "Finances", key: "finances", show: (u) => hasAccess(u, "finance") },
  { href: "marketing.html", label: "Marketing", key: "marketing", show: (u) => u.role === "owner" },
  { href: "coupons.html", label: "Codes promo", key: "coupons", show: (u) => u.role === "owner" },
  { href: "rapports.html", label: "Rapports", key: "rapports", show: (u) => u.role === "owner" || hasAccess(u, "produits") || hasAccess(u, "finance") },
  { href: "employes.html", label: "Employés", key: "employes", show: (u) => u.role === "owner" },
  { href: "plans.html", label: "Mon abonnement", key: "plans", show: (u) => u.role === "owner" },
  { href: "support.html", label: "Support", key: "support", show: () => true },
  { href: "boutique.html", label: "Ma boutique", key: "boutique", show: (u) => u.role === "owner" },
];

function renderLayout(activeKey, pageTitle, pageSub) {
  document.body.insertAdjacentHTML("afterbegin", `
    <div class="mobile-topbar">
      <button id="menuToggle" aria-label="Menu">&#9776;</button>
      <span>MobiBiz</span>
    </div>
    <div class="sidebar-backdrop" id="sidebarBackdrop"></div>
    <div class="app">
      <aside class="sidebar" id="sidebar">
        <div class="sidebar__brand">MobiBiz<span class="dot">.</span></div>
        <div class="sidebar__shop" id="shopNameLabel">Chargement…</div>
        <nav id="sidebarNav"></nav>
        <div class="sidebar__footer">
          <a href="mon-compte.html" class="${activeKey === "mon-compte" ? "active" : ""}" style="display:block;padding:10px 0;color:#c7c9d8;font-size:14.5px">Mon compte</a>
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
            <div id="notifBell" style="position:relative;cursor:pointer;display:none">
              <span style="font-size:20px">🔔</span>
              <span id="notifBadge" class="badge red" style="display:none;position:absolute;top:-6px;right:-10px;min-width:18px;text-align:center;padding:1px 5px"></span>
              <div id="notifDropdown" class="card hidden" style="position:absolute;right:0;top:30px;width:320px;max-height:400px;overflow-y:auto;z-index:60;margin:0"></div>
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

  if (Auth.isImpersonating()) {
    document.body.insertAdjacentHTML("afterbegin", `
      <div style="background:#e0a323;color:#1a1d29;padding:8px 16px;text-align:center;font-size:13.5px;font-weight:600;position:sticky;top:0;z-index:70">
        👁️ Connecté en tant que « ${Auth.impersonatingShopName()} » (accès admin)
        <button id="stopImpersonationBtn" style="margin-left:12px;background:#1a1d29;color:#fff;border:none;padding:4px 12px;border-radius:6px;cursor:pointer;font-size:12.5px">Quitter</button>
      </div>
    `);
    document.getElementById("stopImpersonationBtn").addEventListener("click", () => {
      Auth.stopImpersonation();
      window.location.href = "admin-dashboard.html";
    });
  }

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

  api("/api/boutique").then((shop) => {
    document.getElementById("shopNameLabel").textContent = shop.nom;
  }).catch(() => {});

  api("/api/auth/me").then((user) => {
    if (user.role === "admin") {
      window.location.href = "admin-dashboard.html";
      return;
    }
    const navHtml = NAV_ITEMS.filter((item) => item.show(user)).map(
      (item) => `<a href="${item.href}" class="${item.key === activeKey ? "active" : ""}">${item.label}</a>`
    ).join("");
    document.getElementById("sidebarNav").innerHTML = navHtml;
    initNotifBell();
  }).catch(() => {});
}

function initNotifBell() {
  const bell = document.getElementById("notifBell");
  const badge = document.getElementById("notifBadge");
  const dropdown = document.getElementById("notifDropdown");
  bell.style.display = "block";

  const NOTIF_ICONS = { nouvelle_commande: "🛒", stock_faible: "⚠️", paiement_recu: "💰" };

  async function refreshCount() {
    try {
      const { compte } = await api("/api/notifications/non-lues/compte");
      if (compte > 0) {
        badge.textContent = compte > 9 ? "9+" : compte;
        badge.style.display = "block";
      } else {
        badge.style.display = "none";
      }
    } catch (_) { /* ignore */ }
  }

  async function toggleDropdown() {
    const willOpen = dropdown.classList.contains("hidden");
    dropdown.classList.toggle("hidden");
    if (!willOpen) return;
    dropdown.innerHTML = `<p class="empty">Chargement…</p>`;
    try {
      const notifs = await api("/api/notifications?limit=15");
      dropdown.innerHTML = notifs.length === 0
        ? `<p class="empty">Aucune notification</p>`
        : notifs.map((n) => `
            <div style="padding:9px 4px;border-bottom:1px solid var(--border);${n.lu ? "opacity:.55" : ""}">
              <div style="font-size:13.5px">${NOTIF_ICONS[n.type] || "🔔"} ${n.message}</div>
              <div style="font-size:11px;color:var(--ink-soft);margin-top:2px">${fmtDate(n.created_at)}</div>
            </div>
          `).join("") + `<button class="btn secondary small" id="markAllReadBtn" style="width:100%;margin-top:8px">Tout marquer lu</button>`;
      const markBtn = document.getElementById("markAllReadBtn");
      if (markBtn) {
        markBtn.addEventListener("click", async (e) => {
          e.stopPropagation();
          await api("/api/notifications/lu-tout", { method: "PATCH" });
          await refreshCount();
          dropdown.classList.add("hidden");
        });
      }
    } catch (err) {
      dropdown.innerHTML = `<p class="empty">${err.message}</p>`;
    }
  }

  bell.addEventListener("click", (e) => { e.stopPropagation(); toggleDropdown(); });
  document.addEventListener("click", () => dropdown.classList.add("hidden"));

  refreshCount();
  setInterval(refreshCount, 30000);
}
