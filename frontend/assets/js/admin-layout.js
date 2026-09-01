const ADMIN_NAV_ITEMS = [
  { href: "admin-dashboard.html", label: "Tableau de bord", key: "admin-dashboard" },
  { href: "admin-boutiques.html", label: "Boutiques", key: "admin-boutiques" },
  { href: "admin-utilisateurs.html", label: "Utilisateurs", key: "admin-utilisateurs" },
  { href: "admin-parametres.html", label: "Paramètres", key: "admin-parametres" },
];

function renderAdminLayout(activeKey, pageTitle, pageSub) {
  const navHtml = ADMIN_NAV_ITEMS.map(
    (item) => `<a href="${item.href}" class="${item.key === activeKey ? "active" : ""}">${item.label}</a>`
  ).join("");

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
        <nav>${navHtml}</nav>
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

  api("/api/auth/me").then((user) => {
    if (user.role !== "admin") {
      window.location.href = "dashboard.html";
    }
  }).catch(() => {});
}
