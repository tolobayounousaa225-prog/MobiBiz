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
  { href: "dashboard.html", label: "Tableau de bord", key: "dashboard", icon: "◧", show: () => true },
  { href: "produits.html", label: "Produits", key: "produits", icon: "◫", show: (u) => hasAccess(u, "produits"), badgeKey: "avis" },
  { href: "stock.html", label: "Stock", key: "stock", icon: "▤", show: (u) => hasAccess(u, "stock"), badgeKey: "stock" },
  { href: "clients.html", label: "Clients", key: "clients", icon: "◎", show: () => true },
  { href: "commandes.html", label: "Commandes", key: "commandes", icon: "▥", show: (u) => hasAccess(u, "commandes"), badgeKey: "commandes" },
  { href: "finances.html", label: "Finances", key: "finances", icon: "◐", show: (u) => hasAccess(u, "finance") },
  { href: "marketing.html", label: "Marketing", key: "marketing", icon: "↗", show: (u) => u.role === "owner", section: "Croissance" },
  { href: "coupons.html", label: "Codes promo", key: "coupons", icon: "%", show: (u) => u.role === "owner", section: "Croissance" },
  { href: "rapports.html", label: "Rapports", key: "rapports", icon: "▦", show: (u) => u.role === "owner" || hasAccess(u, "produits") || hasAccess(u, "finance"), section: "Croissance" },
  { href: "employes.html", label: "Employés", key: "employes", icon: "◍", show: (u) => u.role === "owner", section: "Compte" },
  { href: "plans.html", label: "Mon abonnement", key: "plans", icon: "◆", show: (u) => u.role === "owner", section: "Compte" },
  { href: "support.html", label: "Support", key: "support", icon: "?", show: () => true, section: "Compte" },
  { href: "boutique.html", label: "Ma boutique", key: "boutique", icon: "⚑", show: (u) => u.role === "owner", section: "Compte" },
];

const PLAN_LABELS = { free: "Gratuit", starter: "Starter", pro: "Pro", business: "Business", enterprise: "Entreprise" };
const SUBSCRIPTION_STATUS_LABELS = { essai: "essai", actif: "actif", suspendu: "suspendu" };

function renderLayout(activeKey, pageTitle, pageSub) {
  document.body.classList.add("shop-app");
  document.body.insertAdjacentHTML("afterbegin", `
    <div class="mobile-topbar">
      <button id="menuToggle" aria-label="Menu">&#9776;</button>
      <span>MobiBiz</span>
    </div>
    <div class="sidebar-backdrop" id="sidebarBackdrop"></div>
    <div class="app">
      <aside class="sidebar" id="sidebar">
        <div class="sidebar__brand">MobiBiz<span class="dot">.</span></div>
        <div class="shop-chip" id="shopChip">
          <div class="name" id="shopNameLabel">Chargement…</div>
        </div>
        <nav id="sidebarNav" class="nav"></nav>
        <div class="sidebar__footer">
          <a href="mon-compte.html" class="${activeKey === "mon-compte" ? "active" : ""}">Mon compte</a>
          <button id="logoutBtn">Déconnexion</button>
        </div>
      </aside>
      <main class="main">
        <div id="accountAlertBar"></div>
        <div class="topbar">
          <div>
            <h1>${pageTitle}</h1>
            ${pageSub ? `<p class="sub">${pageSub}</p>` : ""}
          </div>
          <div class="topbar-actions" id="topbarActions" style="display:flex;align-items:center;gap:10px">
            <div id="notifBell" class="bell" style="display:none">
              🔔
              <span id="notifBadge" class="dot" style="display:none"></span>
              <div id="notifDropdown" class="card hidden" style="position:absolute;right:0;top:44px;width:320px;max-height:400px;overflow-y:auto;z-index:60;margin:0"></div>
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
    const statusLabel = SUBSCRIPTION_STATUS_LABELS[shop.abonnement_statut] || shop.abonnement_statut;
    const planLabel = PLAN_LABELS[shop.abonnement_plan] || shop.abonnement_plan;
    document.getElementById("shopChip").insertAdjacentHTML("beforeend", `
      <div class="plan"><span class="dot ${shop.abonnement_statut === "suspendu" ? "danger" : shop.abonnement_statut === "essai" ? "warning" : ""}"></span> Plan ${escapeHtml(planLabel)} · ${escapeHtml(statusLabel)}</div>
    `);
    renderAccountAlert(shop);
  }).catch(() => {});

  api("/api/auth/me").then((user) => {
    if (user.role === "admin") {
      window.location.href = "admin-dashboard.html";
      return;
    }
    let navHtml = "";
    let currentSection = null;
    NAV_ITEMS.filter((item) => item.show(user)).forEach((item) => {
      if (item.section !== currentSection) {
        currentSection = item.section;
        if (currentSection) navHtml += `<div class="nav-sec">${currentSection}</div>`;
      }
      navHtml += `<a href="${item.href}" class="${item.key === activeKey ? "active" : ""}"><span class="ic">${item.icon}</span> ${item.label}${
        item.badgeKey ? `<span class="nav-count hidden" data-nav-badge="${item.badgeKey}"></span>` : ""
      }</a>`;
    });
    document.getElementById("sidebarNav").innerHTML = navHtml;
    initNotifBell();
    initPendingActionBadges();
  }).catch(() => {});
}

function renderAccountAlert(shop) {
  const bar = document.getElementById("accountAlertBar");
  if (!bar) return;
  const today = new Date().toISOString().slice(0, 10);

  if (shop.abonnement_statut === "essai" && shop.essai_expire_le) {
    const joursRestants = Math.ceil((new Date(shop.essai_expire_le) - new Date(today)) / 86400000);
    if (joursRestants <= 3) {
      const texte = joursRestants <= 0
        ? "Votre essai gratuit se termine aujourd'hui."
        : `Votre essai gratuit se termine dans ${joursRestants} jour(s) (${fmtDate(shop.essai_expire_le)}).`;
      bar.innerHTML = `
        <div class="alert-bar warning">
          <span>⏳ ${texte} Choisissez un plan pour continuer sans interruption.</span>
          <a href="plans.html" class="btn small">Voir les plans</a>
        </div>
      `;
      return;
    }
  }

  if (shop.abonnement_statut === "actif" && shop.prochain_paiement_le && shop.prochain_paiement_le < today) {
    bar.innerHTML = `
      <div class="alert-bar danger">
        <span>⚠️ Votre paiement d'abonnement est en retard depuis le ${fmtDate(shop.prochain_paiement_le)}. Réglez rapidement pour éviter une suspension.</span>
        <a href="boutique.html" class="btn small">Régler mon abonnement</a>
      </div>
    `;
    return;
  }

  bar.innerHTML = "";
}

function initPendingActionBadges() {
  const badges = document.querySelectorAll("[data-nav-badge]");
  if (badges.length === 0) return;

  async function refresh() {
    try {
      const actions = await api("/api/boutique/actions-en-attente");
      badges.forEach((el) => {
        const count = actions[el.dataset.navBadge] || 0;
        if (count > 0) {
          el.textContent = count > 9 ? "9+" : count;
          el.classList.remove("hidden");
        } else {
          el.classList.add("hidden");
        }
      });
    } catch (_) { /* ignore */ }
  }

  refresh();
  setInterval(refresh, 30000);
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
              <div style="font-size:13.5px">${NOTIF_ICONS[n.type] || "🔔"} ${escapeHtml(n.message)}</div>
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
      dropdown.innerHTML = `<p class="empty">${escapeHtml(err.message)}</p>`;
    }
  }

  bell.addEventListener("click", (e) => { e.stopPropagation(); toggleDropdown(); });
  document.addEventListener("click", () => dropdown.classList.add("hidden"));

  refreshCount();
  setInterval(refreshCount, 30000);
}
