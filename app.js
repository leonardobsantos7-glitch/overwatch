
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

const normalize = value =>
  String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .trim();

const makeId = name =>
  normalize(name).replace(/[^a-z0-9]+/g, "-");

function parseDate(date) {
  if (!date) return 0;

  const months = {
    janeiro: 0, fevereiro: 1, marco: 2, março: 2,
    abril: 3, maio: 4, junho: 5, julho: 6,
    agosto: 7, setembro: 8, outubro: 9,
    novembro: 10, dezembro: 11
  };

  const match = String(date).match(
    /(\d{1,2})\s+de\s+([a-zçã]+)\s+de\s+(\d{4})/i
  );

  if (match) {
    const day = Number(match[1]);
    const month = months[normalize(match[2])];
    const year = Number(match[3]);

    if (month !== undefined) {
      return new Date(year, month, day).getTime();
    }
  }

  const parsed = Date.parse(date);
  return Number.isNaN(parsed) ? 0 : parsed;
}

// Carrega os bancos de dados
async function loadDatabase() {
  try {
    const responses = await Promise.all([
      fetch("heroes.json"),
      fetch("patches.json"),
      fetch("changes.json")
    ]);

    if (responses.some(response => !response.ok)) {
      throw new Error(
        "Não foi possível carregar um ou mais arquivos JSON."
      );
    }

    const [heroesData, patchesData, changesData] =
      await Promise.all(responses.map(response => response.json()));

    heroes = Array.isArray(heroesData)
      ? heroesData
      : heroesData.heroes || [];

    patches = Array.isArray(patchesData)
      ? patchesData
      : patchesData.patches || [];

    const changeRecords = Array.isArray(changesData)
      ? changesData
      : changesData.records || [];

    // Converte os registros novos para o formato usado pelo site
    const importedChanges = changeRecords.map((record, index) => {
      const valueChanges = record.value_changes || [];

      const values = valueChanges.map(change => ({
        oldValue: change.old_value,
        newValue: change.new_value,
        text: change.text
      }));

      return {
        id: `official-${index}-${makeId(record.hero)}-${record.date || ""}`,
        hero: record.hero || "Herói não identificado",
        heroId: makeId(record.hero),
        date: record.date || "",
        patch: record.patch_title || "Nota oficial",
        title: record.patch_title || "Alteração",
        ability: record.category === "hero_update"
          ? "Balanceamento"
          : "Atualização",
        change: record.raw_text || "",
        summary: record.raw_text || "",
        oldValue: values.length ? values[0].oldValue : undefined,
        newValue: values.length ? values[0].newValue : undefined,
        valueChanges: values,
        mode: "Overwatch",
        source: record.source || "",
        category: record.category || ""
      };
    });

    // Combina o histórico antigo com os novos registros oficiais
    patches = [...patches, ...importedChanges];

    // Inclui automaticamente heróis encontrados no histórico
    const knownHeroes = new Set(
      heroes.map(hero => normalize(hero.name))
    );

    const discoveredHeroes = [
      ...new Set(
        importedChanges
          .map(patch => patch.hero)
          .filter(name => name && name !== "Herói não identificado")
      )
    ];

    discoveredHeroes.forEach(name => {
      if (!knownHeroes.has(normalize(name))) {
        heroes.push({
          id: makeId(name),
          name,
          role: "Não cadastrada",
          abilities: [],
          history: []
        });
      }
    });

    renderHeroes();
    renderPatches();

  } catch (error) {
    heroesContainer.innerHTML = `
      <p>Erro ao carregar o banco de dados.
      Verifique se heroes.json, patches.json e changes.json
      estão publicados na raiz do repositório.</p>
    `;

    console.error(error);
  }
}

// Histórico completo de um herói
function getHeroHistory(hero) {
  const individualHistory = [
    ...(hero.history || []),
    ...(hero.stadium?.history || [])
  ];

  const globalHistory = patches.filter(patch =>
    normalize(patch.heroId) === normalize(hero.id) ||
    normalize(patch.hero) === normalize(hero.name)
  );

  const combined = [...individualHistory, ...globalHistory];
  const unique = new Map();

  combined.forEach((patch, index) => {
    const key = patch.id ||
      `${patch.date || ""}-${patch.mode || "Overwatch"}-${patch.ability || patch.title || ""}-${patch.change || ""}-${index}`;

    if (!unique.has(key)) {
      unique.set(key, patch);
    }
  });

  return [...unique.values()].sort((a, b) =>
    parseDate(b.date) - parseDate(a.date)
  );
}

// Cards dos heróis
function renderHeroes() {
  const query = normalize(searchInput.value);

  const filteredHeroes = heroes.filter(hero => {
    const searchableText = [
      hero.name,
      hero.role,
      ...(hero.abilities || [])
    ].join(" ");

    return normalize(searchableText).includes(query);
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
          ${escapeHTML(hero.role || "Função não cadastrada")}
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

// Histórico recente na página principal
function renderPatches() {
  const allPatches = patches
    .filter(patch => patch.hero || patch.heroId)
    .sort((a, b) => parseDate(b.date) - parseDate(a.date));

  if (allPatches.length === 0) {
    patchesContainer.innerHTML = `
      <p>O histórico ainda não foi importado.</p>
    `;
    return;
  }

  patchesContainer.innerHTML = allPatches
    .slice(0, 30)
    .map(patch => {
      const values = patch.valueChanges || [];

      return `
        <article class="patch">

          <h3>
            ${escapeHTML(patch.hero || patch.heroName || "Herói")}
            — ${escapeHTML(patch.title || patch.ability || "Alteração")}
          </h3>

          <p class="muted">
            ${escapeHTML(patch.date || "Data não informada")}
            · ${escapeHTML(patch.mode || "Overwatch")}
          </p>

          <p>
            ${escapeHTML(patch.change || patch.summary || "")}
          </p>

          ${values.length ? `
            <div class="value-changes">
              <strong>Valores registrados:</strong>
              ${values.map(value => `
                <p>
                  ${escapeHTML(value.text || "")}
                  ${value.oldValue !== undefined ||
                    value.newValue !== undefined ? `
                    <br>
                    <strong>
                      ${escapeHTML(value.oldValue ?? "—")}
                      → ${escapeHTML(value.newValue ?? "—")}
                    </strong>
                  ` : ""}
                </p>
              `).join("")}
            </div>
          ` : patch.oldValue !== undefined ||
               patch.newValue !== undefined ? `
            <p>
              <strong>Valores:</strong>
              ${escapeHTML(patch.oldValue ?? "—")}
              → ${escapeHTML(patch.newValue ?? "—")}
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
      `;
    }).join("");
}

// Abre a ficha do herói
function openHero(heroId) {
  const hero = heroes.find(item =>
    String(item.id) === String(heroId)
  );

  if (!hero) return;

  const history = getHeroHistory(hero);

  const normalHistory = history.filter(
    patch => patch.mode !== "Stadium"
  );

  const stadiumHistory = history.filter(
    patch => patch.mode === "Stadium"
  );

  let modal = document.querySelector("#hero-modal");

  if (!modal) {
    modal = document.createElement("div");
    modal.id = "hero-modal";
    modal.className = "hero-modal";
    document.body.appendChild(modal);
  }

  modal.innerHTML = `
    <div class="hero-modal-backdrop"></div>

    <section class="hero-modal-content">

      <button class="hero-modal-close"
        aria-label="Fechar">×</button>

      <span class="role">
        ${escapeHTML(hero.role || "Função não cadastrada")}
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

// Exibe as alterações na ficha
function renderHistory(history) {
  if (history.length === 0) {
    return `
      <p class="muted">
        Nenhuma alteração importada nesta seção.
        Isso não significa que o herói nunca recebeu mudanças.
      </p>
    `;
  }

  return history.map(patch => {
    const values = patch.valueChanges || [];

    return `
      <article class="history-item">

        <p class="muted">
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

        ${values.length ? `
          <div class="value-changes">
            ${values.map(value => `
              <p>
                ${escapeHTML(value.text || "")}
                ${value.oldValue !== undefined ||
                  value.newValue !== undefined ? `
                  <br>
                  <strong>
                    Antes: ${escapeHTML(value.oldValue ?? "—")}
                    <br>
                    Depois: ${escapeHTML(value.newValue ?? "—")}
                  </strong>
                ` : ""}
              </p>
            `).join("")}
          </div>
        ` : patch.oldValue !== undefined ||
             patch.newValue !== undefined ? `
          <p>
            <strong>Antes:</strong>
            ${escapeHTML(patch.oldValue ?? "—")}
            <br>
            <strong>Depois:</strong>
            ${escapeHTML(patch.newValue ?? "—")}
          </p>
        ` : ""}

        ${patch.source ? `
          <a href="${escapeHTML(patch.source)}"
             target="_blank"
             rel="noopener noreferrer">
            Consultar nota oficial
          </a>
        ` : ""}

      </article>
    `;
  }).join("");
}

// Fecha a ficha
function closeHero() {
  const modal = document.querySelector("#hero-modal");

  if (modal) {
    modal.classList.remove("active");
    document.body.style.overflow = "";
  }
}

// Eventos
searchInput.addEventListener("input", renderHeroes);

document.addEventListener("keydown", event => {
  if (event.key === "Escape") {
    closeHero();
  }
});

// Inicialização
loadDatabase();
