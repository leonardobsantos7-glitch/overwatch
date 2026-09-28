
const heroesContainer = document.querySelector("#heroes");
const patchesContainer = document.querySelector("#patches");
const searchInput = document.querySelector("#search");

let heroes = [];
let patches = [];

const escapeHTML = (value = "") =>
  String(value).replace(/[&<>"']/g, char => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;"
  }[char]));

// Carrega o banco de dados
async function loadDatabase() {
  try {
    const [heroesResponse, patchesResponse] = await Promise.all([
      fetch("data/heroes.json"),
      fetch("data/patches.json")
    ]);

    if (!heroesResponse.ok || !patchesResponse.ok) {
      throw new Error("Não foi possível carregar os arquivos JSON.");
    }

    heroes = await heroesResponse.json();
    patches = await patchesResponse.json();

    renderHeroes();
    renderPatches();
  } catch (error) {
    heroesContainer.innerHTML = `
      <p>Erro ao carregar o banco de dados.
      Verifique os arquivos JSON.</p>
    `;

    console.error(error);
  }
}

// Junta o histórico geral com o histórico individual do herói
function getHeroHistory(hero) {
  const individualHistory = [
    ...(hero.history || []),
    ...(hero.stadium?.history || [])
  ];

  const globalHistory = patches.filter(patch =>
    patch.heroId === hero.id ||
    patch.hero === hero.name
  );

  const combined = [...individualHistory, ...globalHistory];

  // Evita duplicar registros que tenham o mesmo identificador
  const unique = new Map();

  combined.forEach((patch, index) => {
    const key = patch.id ||
      `${patch.date || ""}-${patch.mode || "Overwatch"}-${patch.ability || patch.title || ""}-${index}`;

    unique.set(key, patch);
  });

  return [...unique.values()].sort((a, b) =>
    (b.date || "").localeCompare(a.date || "")
  );
}

// Cria os cards dos heróis
function renderHeroes() {
  const query = searchInput.value
    .trim()
    .toLocaleLowerCase("pt-BR");

  const filteredHeroes = heroes.filter(hero => {
    const searchableText = [
      hero.name,
      hero.role,
      ...(hero.abilities || [])
    ].join(" ").toLocaleLowerCase("pt-BR");

    return searchableText.includes(query);
  });

  if (filteredHeroes.length === 0) {
    heroesContainer.innerHTML =
      "<p>Nenhum herói encontrado.</p>";
    return;
  }

  heroesContainer.innerHTML = filteredHeroes.map(hero => {
    const history = getHeroHistory(hero);

    return `
      <button class="hero-card"
        data-hero-id="${escapeHTML(hero.id)}">

        <h3>${escapeHTML(hero.name)}</h3>

        <span class="role">
          ${escapeHTML(hero.role)}
        </span>

        <div class="card-bottom">
          <span>Alterações registradas</span>
          <strong class="count">${history.length}</strong>
        </div>

      </button>
    `;
  }).join("");

  document.querySelectorAll("[data-hero-id]")
    .forEach(card => {
      card.addEventListener("click", () => {
        openHero(card.dataset.heroId);
      });
    });
}

// Mostra as alterações mais recentes na página principal
function renderPatches() {
  const allPatches = heroes.flatMap(hero =>
    getHeroHistory(hero).map(patch => ({
      ...patch,
      heroName: hero.name
    }))
  );

  const sorted = allPatches.sort((a, b) =>
    (b.date || "").localeCompare(a.date || "")
  );

  if (sorted.length === 0) {
    patchesContainer.innerHTML = `
      <p>
        O histórico de patches ainda não foi importado.
        Os contadores mostram apenas os registros
        disponíveis no banco atual.
      </p>
    `;
    return;
  }

  patchesContainer.innerHTML = sorted
    .slice(0, 20)
    .map(patch => `
      <article class="patch">

        <h3>
          ${escapeHTML(patch.heroName)}
          — ${escapeHTML(patch.title || patch.ability || "Alteração")}
        </h3>

        <p>
          ${escapeHTML(patch.date || "Data não informada")}
          · ${escapeHTML(patch.mode || "Overwatch")}
        </p>

        <p>
          ${escapeHTML(patch.change || patch.summary || "")}
        </p>

        ${patch.oldValue !== undefined ||
          patch.newValue !== undefined ? `
          <p>
            <strong>Valores:</strong>
            ${escapeHTML(patch.oldValue ?? "—")}
            →
            ${escapeHTML(patch.newValue ?? "—")}
          </p>
        ` : ""}

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
            Fonte oficial
          </a>
        ` : ""}

      </article>
    `).join("");
}

// Cria a janela de detalhes do herói
function openHero(heroId) {
  const hero = heroes.find(item => item.id === heroId);

  if (!hero) return;

  const history = getHeroHistory(hero);

  let modal = document.querySelector("#hero-modal");

  if (!modal) {
    modal = document.createElement("div");
    modal.id = "hero-modal";
    modal.className = "hero-modal";

    document.body.appendChild(modal);
  }

  const normalHistory = history.filter(
    patch => patch.mode !== "Stadium"
  );

  const stadiumHistory = history.filter(
    patch => patch.mode === "Stadium"
  );

  modal.innerHTML = `
    <div class="hero-modal-backdrop"></div>

    <section class="hero-modal-content">

      <button class="hero-modal-close"
        aria-label="Fechar">×</button>

      <span class="role">
        ${escapeHTML(hero.role)}
      </span>

      <h2>${escapeHTML(hero.name)}</h2>

      <p>
        Lançamento:
        ${escapeHTML(hero.release || "Data não cadastrada")}
      </p>

      <h3>Habilidades</h3>

      <ul>
        ${(hero.abilities || []).map(ability => `
          <li>${escapeHTML(ability)}</li>
        `).join("") || "<li>Dados ainda não cadastrados.</li>"}
      </ul>

      <h3>Histórico de Overwatch</h3>

      ${renderHistory(normalHistory)}

      <h3>Histórico de Stadium</h3>

      ${renderHistory(stadiumHistory)}

    </section>
  `;

  modal.classList.add("active");
  document.body.style.overflow = "hidden";

  modal.querySelector(".hero-modal-close")
    .addEventListener("click", closeHero);

  modal.querySelector(".hero-modal-backdrop")
    .addEventListener("click", closeHero);
}

// Formata uma lista de alterações
function renderHistory(history) {
  if (history.length === 0) {
    return `
      <p>
        Nenhuma alteração importada nesta seção.
        Isso não significa que o herói nunca recebeu
        mudanças.
      </p>
    `;
  }

  return history.map(patch => `
    <article class="history-item">

      <p>
        <strong>
          ${escapeHTML(patch.date || "Data desconhecida")}
        </strong>
        · ${escapeHTML(patch.patch || "Patch não identificado")}
      </p>

      <h4>
        ${escapeHTML(patch.ability || patch.title || "Alteração")}
      </h4>

      <p>
        ${escapeHTML(patch.change || patch.summary || "")}
      </p>

      ${patch.oldValue !== undefined ||
        patch.newValue !== undefined ? `
        <p>
          <strong>Antes:</strong>
          ${escapeHTML(patch.oldValue ?? "—")}
          <br>
          <strong>Depois:</strong>
          ${escapeHTML(patch.newValue ?? "—")}
        </p>
      ` : ""}

      <p>
        <strong>Justificativa oficial:</strong>
        ${escapeHTML(
          patch.rationale ||
          "Justificativa não registrada."
        )}
      </p>

      ${patch.source ? `
        <a href="${escapeHTML(patch.source)}"
           target="_blank"
           rel="noopener noreferrer">
          Consultar nota oficial
        </a>
      ` : ""}

    </article>
  `).join("");
}

// Fecha a ficha
function closeHero() {
  const modal = document.querySelector("#hero-modal");

  if (modal) {
    modal.classList.remove("active");
    document.body.style.overflow = "";
  }
}

// Eventos da interface
searchInput.addEventListener("input", renderHeroes);

document.addEventListener("keydown", event => {
  if (event.key === "Escape") {
    closeHero();
  }
});

// Inicialização
loadDatabase();
