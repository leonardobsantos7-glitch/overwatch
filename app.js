
const HEROES_URL = "data/heroes.json";
const PATCHES_URL = "data/patches.json";

let heroes = [];
let patches = [];

const $ = (selector) => document.querySelector(selector);

function escapeHTML(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;"
  })[char]);
}

async function loadDatabase() {
  try {
    const [heroesResponse, patchesResponse] = await Promise.all([
      fetch(HEROES_URL),
      fetch(PATCHES_URL)
    ]);

    if (!heroesResponse.ok || !patchesResponse.ok) {
      throw new Error("Não foi possível carregar os arquivos JSON.");
    }

    heroes = await heroesResponse.json();
    patches = await patchesResponse.json();

    renderHeroes();
    renderPatches();
    updateStats();

  } catch (error) {
    console.error(error);

    if ($("#heroes")) {
      $("#heroes").innerHTML =
        "<p>Erro ao carregar o banco de dados. Confira os arquivos JSON.</p>";
    }
  }
}

function updateStats() {
  const heroCount = $("#hero-count");
  const patchCount = $("#patch-count");

  if (heroCount) {
    heroCount.textContent = `${heroes.length} heróis cadastrados`;
  }

  if (patchCount) {
    patchCount.textContent = `${patches.length} alterações importadas`;
  }
}

function renderHeroes() {
  const container = $("#heroes");

  if (!container) return;

  const searchInput = $("#search");
  const roleFilter = $("#role-filter");

  const query = (searchInput?.value || "")
    .trim()
    .toLocaleLowerCase("pt-BR");

  const selectedRole = roleFilter?.value || "";

  const filteredHeroes = heroes.filter((hero) => {
    const searchableText = [
      hero.name,
      hero.role,
      ...(hero.abilities || [])
    ].join(" ").toLocaleLowerCase("pt-BR");

    const matchesSearch = searchableText.includes(query);
    const matchesRole = !selectedRole || hero.role === selectedRole;

    return matchesSearch && matchesRole;
  });

  if (filteredHeroes.length === 0) {
    container.innerHTML = "<p>Nenhum herói encontrado.</p>";
    return;
  }

  container.innerHTML = filteredHeroes.map((hero) => {
    const normalCount = (hero.history || []).length;
    const stadiumCount = (hero.stadium?.history || []).length;
    const totalCount = normalCount + stadiumCount;

    return `
      <article class="card hero-card"
        data-hero-id="${escapeHTML(hero.id)}"
        tabindex="0"
        role="button"
        aria-label="Abrir ficha de ${escapeHTML(hero.name)}">

        <h3>${escapeHTML(hero.name)}</h3>

        <span class="tag">
          ${escapeHTML(hero.role)}
        </span>

        <p class="muted">
          ${(hero.abilities || []).length} habilidades cadastradas
        </p>

        <div class="card-bottom">
          <span>Alterações registradas</span>
          <strong>${totalCount}</strong>
        </div>
      </article>
    `;
  }).join("");

  container.querySelectorAll("[data-hero-id]").forEach((card) => {
    const open = () => openHero(card.dataset.heroId);

    card.addEventListener("click", open);

    card.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        open();
      }
    });
  });
}

function renderPatches() {
  const container = $("#patches");

  if (!container) return;

  const sortedPatches = [...patches].sort((a, b) =>
    (b.date || "").localeCompare(a.date || "")
  );

  if (sortedPatches.length === 0) {
    container.innerHTML = `
      <div class="patch">
        <strong>Histórico ainda não importado.</strong>
        <p class="muted">
          As alterações serão exibidas aqui após a importação
          e verificação das notas oficiais da Blizzard.
        </p>
      </div>
    `;
    return;
  }

  container.innerHTML = sortedPatches.slice(0, 20).map((patch) => `
    <article class="patch">
      <h3>
        ${escapeHTML(patch.hero || "Herói")}
        — ${escapeHTML(patch.title || patch.patch || "Alteração")}
      </h3>

      <p class="muted">
        ${escapeHTML(patch.date || "Data não informada")}
        · ${escapeHTML(patch.mode || "Overwatch")}
      </p>

      <p>${escapeHTML(patch.change || patch.summary || "")}</p>

      ${patch.rationale ? `
        <p>
          <strong>Justificativa da Blizzard:</strong>
          ${escapeHTML(patch.rationale)}
        </p>
      ` : ""}

      ${patch.source ? `
        <a href="${escapeHTML(patch.source)}"
           target="_blank"
           rel="noopener noreferrer">
          Ver fonte oficial
        </a>
      ` : ""}
    </article>
  `).join("");
}

function createModal() {
  let modal = $("#hero-modal");

  if (modal) return modal;

  modal = document.createElement("div");
  modal.id = "hero-modal";
  modal.className = "hero-modal";

  modal.innerHTML = `
    <div class="hero-modal-backdrop" data-close-modal></div>

    <section class="hero-modal-content"
      role="dialog"
      aria-modal="true"
      aria-labelledby="modal-title">

      <button class="modal-close"
        type="button"
        aria-label="Fechar ficha">
        ×
      </button>

      <div id="hero-detail"></div>
    </section>
  `;

  document.body.appendChild(modal);

  const closeButton = modal.querySelector(".modal-close");

  closeButton.addEventListener("click", closeHero);

  modal.querySelector("[data-close-modal]")
    .addEventListener("click", closeHero);

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closeHero();
  });

  return modal;
}

function openHero(heroId) {
  const hero = heroes.find((item) => item.id === heroId);

  if (!hero) return;

  const modal = createModal();
  const detail = $("#hero-detail");

  const normalHistory = hero.history || [];
  const stadiumHistory = hero.stadium?.history || [];

  detail.innerHTML = `
    <div class="detail-header">
      <span class="tag">${escapeHTML(hero.role)}</span>

      <h2 id="modal-title">
        ${escapeHTML(hero.name)}
      </h2>

      <p>${escapeHTML(hero.summary || "")}</p>

      <p class="muted">
        Lançamento: ${escapeHTML(hero.release || "Não informado")}
      </p>
    </div>

    <section class="detail-section">
      <h3>Habilidades</h3>

      ${
        hero.abilities?.length
          ? `<ul>
              ${hero.abilities.map((ability) =>
                `<li>${escapeHTML(ability)}</li>`
              ).join("")}
            </ul>`
          : `<p class="muted">
              Habilidades ainda não cadastradas.
            </p>`
      }
    </section>

    <section class="detail-section">
      <h3>Histórico de Overwatch</h3>

      ${renderHeroHistory(normalHistory)}
    </section>

    <section class="detail-section">
      <h3>Histórico de Stadium</h3>

      ${renderHeroHistory(stadiumHistory)}
    </section>
  `;

  modal.classList.add("active");
  document.body.style.overflow = "hidden";

  modal.querySelector(".modal-close").focus();
}

function renderHeroHistory(history) {
  if (!history.length) {
    return `
      <p class="muted">
        Nenhuma alteração importada ainda.
        Isso não significa que o herói nunca recebeu mudanças.
      </p>
    `;
  }

  const sortedHistory = [...history].sort((a, b) =>
    (b.date || "").localeCompare(a.date || "")
  );

  return sortedHistory.map((change) => `
    <article class="history-item">

      <p class="muted">
        ${escapeHTML(change.date || "Data não informada")}
        · ${escapeHTML(change.patch || "Patch não identificado")}
      </p>

      <h4>
        ${escapeHTML(change.ability || change.title || "Alteração")}
      </h4>

      <p>
        ${escapeHTML(change.change || change.summary || "")}
      </p>

      ${
        change.oldValue !== undefined ||
        change.newValue !== undefined
          ? `<p>
              <strong>Valor:</strong>
              ${escapeHTML(change.oldValue ?? "—")}
              →
              ${escapeHTML(change.newValue ?? "—")}
            </p>`
          : ""
      }

      ${
        change.rationale
          ? `<p>
              <strong>Justificativa oficial:</strong>
              ${escapeHTML(change.rationale)}
            </p>`
          : `<p class="muted">
              Justificativa oficial não registrada.
            </p>`
      }

      ${
        change.source
          ? `<a href="${escapeHTML(change.source)}"
                target="_blank"
                rel="noopener noreferrer">
                Consultar fonte oficial
             </a>`
          : ""
      }

    </article>
  `).join("");
}

function closeHero() {
  const modal = $("#hero-modal");

  if (!modal) return;

  modal.classList.remove("active");
  document.body.style.overflow = "";
}

$("#search")?.addEventListener("input", renderHeroes);

$("#role-filter")?.addEventListener("change", renderHeroes);

loadDatabase();
