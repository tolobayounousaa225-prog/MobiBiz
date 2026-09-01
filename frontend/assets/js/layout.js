const NAV_ITEMS = [
  { href: "dashboard.html", label: "Tableau de bord", key: "dashboard" },
  { href: "produits.html", label: "Produits", key: "produits" },
  { href: "stock.html", label: "Stock", key: "stock" },
  { href: "clients.html", label: "Clients", key: "clients" },
  { href: "commandes.html", label: "Commandes", key: "commandes" },
  { href: "rapports.html", label: "Rapports", key: "rapports" },
  { href: "boutique.html", label: "Ma boutique", key: "boutique" },
];

function renderLayout(activeKey, pageTitle, pageSub) {
  const navHtml = NAV_ITEMS.map(
    (item) => `<a href="${item.href}" class="${item.key === activeKey ? "active" : ""}">${item.label}</a>`
  ).join("");

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
        <nav>${navHtml}</nav>
        <div class="sidebar__footer">
          <button id="logoutBtn">Déconnexion</button>
        </div>
      </aside>
      <main class="main">
        <div class="topbar">
          <div>
            <h1>${pageTitle}</h1>
            ${pageSub ? `<p class="sub">${pageSub}</p>` : ""}
          </div>
          <div class="topbar-actions" id="topbarActions"></div>
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

  api("/api/boutique").then((shop) => {
    document.getElementById("shopNameLabel").textContent = shop.nom;
  }).catch(() => {});
}
