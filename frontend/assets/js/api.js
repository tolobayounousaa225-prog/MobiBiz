const API_BASE = (location.hostname === "localhost" || location.hostname === "127.0.0.1")
  ? "http://127.0.0.1:8010"
  : "https://mobibiz-backend-production.up.railway.app";

const Auth = {
  getToken() { return localStorage.getItem("mobibiz_token"); },
  setToken(t) { localStorage.setItem("mobibiz_token", t); },
  clear() { localStorage.removeItem("mobibiz_token"); },
  requireAuth() {
    if (!this.getToken()) window.location.href = "index.html";
  },
  // "Connexion en tant que" (admin -> propriétaire) : on garde le token admin de
  // côté pour pouvoir revenir, plutôt que de forcer une reconnexion.
  startImpersonation(shopToken, shopName) {
    localStorage.setItem("mobibiz_admin_backup_token", this.getToken());
    localStorage.setItem("mobibiz_impersonating_shop", shopName);
    this.setToken(shopToken);
  },
  isImpersonating() { return !!localStorage.getItem("mobibiz_admin_backup_token"); },
  impersonatingShopName() { return localStorage.getItem("mobibiz_impersonating_shop") || ""; },
  stopImpersonation() {
    const backup = localStorage.getItem("mobibiz_admin_backup_token");
    if (backup) this.setToken(backup);
    localStorage.removeItem("mobibiz_admin_backup_token");
    localStorage.removeItem("mobibiz_impersonating_shop");
  },
};

function fmtFCFA(n) {
  const value = Number(n || 0);
  return value.toLocaleString("fr-FR", { maximumFractionDigits: 0 }) + " FCFA";
}

function fmtDate(iso) {
  if (!iso) return "-";
  const d = new Date(iso);
  return d.toLocaleDateString("fr-FR", { day: "2-digit", month: "2-digit", year: "numeric" });
}

async function api(path, { method = "GET", body, formData, isBlob = false } = {}) {
  const headers = {};
  const token = Auth.getToken();
  if (token) headers["Authorization"] = "Bearer " + token;
  // Ne jamais fixer Content-Type pour FormData : le navigateur doit poser lui-même
  // la frontière multipart, sinon la requête est mal formée côté serveur.
  if (body !== undefined) headers["Content-Type"] = "application/json";

  const res = await fetch(API_BASE + path, {
    method,
    headers,
    body: formData || (body !== undefined ? JSON.stringify(body) : undefined),
  });

  if (!res.ok) {
    let detail = "Une erreur est survenue";
    try {
      const data = await res.json();
      detail = typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail);
    } catch (_) { /* ignore */ }

    // Un 401 sur un appel authentifié (token envoyé mais rejeté) veut dire
    // session expirée : on déconnecte. Un 401 sans token (ex: mauvais mot de
    // passe sur /auth/login) est une erreur normale à afficher, pas une
    // session expirée — ne pas rediriger dans ce cas.
    if (res.status === 401 && token) {
      Auth.clear();
      window.location.href = "index.html";
    }
    // 402 = boutique suspendue par l'administrateur (voir deps.get_current_shop) :
    // rediriger vers une page d'explication plutôt que laisser chaque page
    // afficher une pile de toasts d'erreur peu clairs.
    if (res.status === 402 && !location.pathname.endsWith("compte-suspendu.html")) {
      window.location.href = "compte-suspendu.html";
    }
    throw new Error(detail);
  }

  if (res.status === 204) return null;
  if (isBlob) return res.blob();
  return res.json();
}

function toast(message, type = "") {
  let wrap = document.querySelector(".toast-wrap");
  if (!wrap) {
    wrap = document.createElement("div");
    wrap.className = "toast-wrap";
    document.body.appendChild(wrap);
  }
  const el = document.createElement("div");
  el.className = "toast" + (type ? " " + type : "");
  el.textContent = message;
  wrap.appendChild(el);
  setTimeout(() => el.remove(), 4000);
}

const ORDER_STATUS_LABELS = {
  nouvelle: ["Nouvelle", "gray"],
  confirmee: ["Confirmée", "blue"],
  en_preparation: ["En préparation", "amber"],
  expediee: ["Expédiée", "orange"],
  livree: ["Livrée", "green"],
  terminee: ["Terminée", "green"],
  annulee: ["Annulée", "red"],
  retournee: ["Retournée", "red"],
  echouee: ["Échouée", "red"],
};

const PAIEMENT_STATUS_LABELS = {
  en_attente: ["En attente", "gray"],
  initie: ["Initié", "amber"],
  paye: ["Payé", "green"],
  echoue: ["Échoué", "red"],
};

const ORDER_STATUS_TRANSITIONS = {
  nouvelle: ["confirmee", "annulee"],
  confirmee: ["en_preparation", "annulee"],
  en_preparation: ["expediee", "annulee"],
  expediee: ["livree", "echouee"],
  livree: ["terminee", "retournee"],
  terminee: [],
  annulee: [],
  retournee: [],
  echouee: [],
};

function badge(labelMap, key) {
  const [label, color] = labelMap[key] || [key, "gray"];
  return `<span class="badge ${color}">${label}</span>`;
}

// Badge coloré pour une échéance de paiement d'abonnement (rouge = en retard,
// orange = dans les 5 jours, gris = plus loin). Partagé entre les pages admin.
function paymentDueBadge(dateStr) {
  if (!dateStr) return `<span style="color:var(--ink-soft)">—</span>`;
  const due = new Date(dateStr + "T00:00:00");
  const today = new Date(); today.setHours(0, 0, 0, 0);
  const diffDays = Math.round((due - today) / 86400000);
  const label = fmtDate(dateStr);
  if (diffDays < 0) return `<span class="badge red">${label} (en retard)</span>`;
  if (diffDays <= 5) return `<span class="badge amber">${label}</span>`;
  return `<span class="badge gray">${label}</span>`;
}

const DELIVERY_MODE_LABELS = {
  interne: "Livraison interne",
  partenaire: "Livreur partenaire",
  retrait_boutique: "Retrait en boutique",
};

// Convertit un numéro ivoirien local (07..., 05..., 01..., avec ou sans espaces/tirets)
// au format international sans "+" attendu par l'API wa.me. Un numéro déjà
// international (commence par 225 ou +225) est simplement nettoyé.
function toWhatsAppNumber(phone) {
  const digits = (phone || "").replace(/[^0-9]/g, "");
  if (digits.startsWith("225")) return digits;
  if (digits.startsWith("0")) return "225" + digits.slice(1);
  return digits;
}

function waLink(phone, message) {
  const number = toWhatsAppNumber(phone);
  return `https://wa.me/${number}?text=${encodeURIComponent(message)}`;
}
