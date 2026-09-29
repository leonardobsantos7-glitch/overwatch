
import json
import re
import unicodedata
from datetime import date
from pathlib import Path

INPUT_FILE = Path("archive.json")
OUTPUT_FILE = Path("changes.json")

HEROES = [
    "Ana", "Anran", "Ashe", "Baptiste", "Bastion",
    "Brigitte", "Cassidy", "D.Va", "D.Mon", "Domina",
    "Doomfist", "Echo", "Emre", "Freja", "Genji",
    "Hanzo", "Illari", "Jetpackcat", "Junker Queen",
    "Junkrat", "Juno", "Kiriko", "Lifeweaver", "Lúcio",
    "Mauga", "Mei", "Mercy", "Mizuki", "Moira",
    "Orisa", "Pharah", "Ramattra", "Reaper", "Reinhardt",
    "Roadhog", "Sierra", "Sigma", "Shion", "Sojourn",
    "Soldado: 76", "Sombra", "Symmetra", "Torbjörn",
    "Tracer", "Vendetta", "Winston", "Wrecking Ball",
    "Wuyang", "Zarya", "Zenyatta"
]

ALIASES = {
    "McCree": "Cassidy",
    "Soldier: 76": "Soldado: 76",
    "Soldier 76": "Soldado: 76",
    "Soldier:76": "Soldado: 76",
    "Lucio": "Lúcio",
    "Torbjorn": "Torbjörn",
    "Life Weaver": "Lifeweaver",
    "Jetpack Cat": "Jetpackcat",
    "Junkerqueen": "Junker Queen",
}


def normalize(text):
    text = unicodedata.normalize("NFKD", str(text or ""))
    text = "".join(
        char for char in text
        if not unicodedata.combining(char)
    )
    return re.sub(r"\s+", " ", text).strip().casefold()


HERO_LOOKUP = {
    normalize(hero): hero
    for hero in HEROES
}

for alias, canonical in ALIASES.items():
    HERO_LOOKUP[normalize(alias)] = canonical


def canonical_hero(line):
    return HERO_LOOKUP.get(normalize(line))


def clean_lines(text):
    return [
        line.strip()
        for line in text.splitlines()
        if line.strip()
    ]


def split_articles(text):
    """
    Divide o conteúdo mensal em artigos usando títulos
    e datas das notas oficiais.
    """
    lines = clean_lines(text)
    articles = []
    current = []
    current_date = None
    current_title = None

    date_pattern = re.compile(
        r"^\d{1,2}\s+de\s+"
        r"(janeiro|fevereiro|março|abril|maio|junho|julho|"
        r"agosto|setembro|outubro|novembro|dezembro)"
        r"\s+de\s+\d{4}$",
        re.IGNORECASE
    )

    title_pattern = re.compile(
        r"^(Notas de atualização de Overwatch|"
        r"Atualização de Overwatch)",
        re.IGNORECASE
    )

    def save_article():
        if current:
            articles.append({
                "date": current_date,
                "title": current_title,
                "lines": current.copy()
            })

    for line in lines:
        if date_pattern.match(line):
            save_article()
            current = []
            current_date = line

        elif title_pattern.match(line):
            if current:
                save_article()
                current = []

            current_title = line
            current.append(line)

        elif current_title:
            current.append(line)

    save_article()

    return articles


def extract_value_changes(text):
    """
    Extrai pares de valores de frases que usam
    expressões como 'de X para Y'.
    """
    patterns = [
        (
            r"(?:aumentad[oa]s?|reduzid[oa]s?|alterad[oa]s?)"
            r"\s+de\s+(.+?)\s+para\s+(.+?)(?:[.!;]|$)"
        ),
        (
            r"(?:passou|passaram)\s+de\s+(.+?)"
            r"\s+para\s+(.+?)(?:[.!;]|$)"
        ),
    ]

    results = []

    for line in text.splitlines():
        line = line.strip()

        for pattern in patterns:
            match = re.search(pattern, line, re.IGNORECASE)

            if match:
                results.append({
                    "old_value": match.group(1).strip(),
                    "new_value": match.group(2).strip(),
                    "text": line
                })
                break

    return results


# Cabeçalhos que iniciam seções de Overwatch normal.
NORMAL_HEADERS = {
    normalize("Heróis"),
    normalize("Atualizações dos heróis"),
    normalize("Atualizações de heróis"),
    normalize("Atualizações dos Heróis"),
}

# Cabeçalhos que iniciam seções de Stadium.
STADIUM_HEADERS = {
    normalize("Estádio"),
    normalize("Stadium"),
    normalize("Atualizações do Estádio"),
    normalize("Atualizações de Estádio"),
    normalize("Atualizações do Stadium"),
    normalize("Atualizações de Stadium"),
    normalize("Atualizações do Estadio"),
    normalize("Correções de bugs do Estádio"),
    normalize("Correções de bugs do Stadium"),
}

# Cabeçalhos que encerram uma seção de heróis.
# Tanque, Dano e Suporte NÃO entram aqui porque
# podem ser categorias dentro da própria seção Stadium.
END_HEADERS = {
    normalize("Correção de bugs"),
    normalize("Correções de bugs"),
    normalize("Correções de bugs gerais"),
    normalize("Atualizações Gerais"),
    normalize("Atualizações gerais"),
    normalize("Atualizações de mapas"),
    normalize("Mapas"),
    normalize("Workshop"),
    normalize("Atualizações no Jogo Competitivo"),
    normalize("Atualizações de eventos"),
    normalize("Atualizações do Arcade"),
    normalize("Atualizações de jogabilidade"),
}


# Cabeçalhos de categoria dentro de Stadium.
# Eles encerram o bloco do herói atual, mas não
# encerram a seção inteira.
CATEGORY_HEADERS = {
    normalize("Tanque"),
    normalize("Dano"),
    normalize("Suporte"),
    normalize("Geral"),
}


def extract_hero_blocks(article):
    """
    Extrai os blocos de cada herói e identifica
    se pertencem a Overwatch normal ou Stadium.
    """
    lines = article["lines"]
    blocks = []

    active = False
    mode = None
    current_hero = None
    current_lines = []

    def save_current():
        if current_hero and current_lines:
            raw_text = "\n".join(current_lines).strip()

            if raw_text:
                blocks.append({
                    "hero": current_hero,
                    "mode": mode,
                    "raw_text": raw_text
                })

    for line in lines:
        normalized_line = normalize(line)

        # Início de uma seção Stadium.
        if normalized_line in STADIUM_HEADERS:
            save_current()

            current_hero = None
            current_lines = []
            mode = "Stadium"
            active = True
            continue

        # Início de uma seção de heróis normal.
        if normalized_line in NORMAL_HEADERS:
            save_current()

            current_hero = None
            current_lines = []
            mode = "Overwatch"
            active = True
            continue

        if not active:
            continue

        # Categorias internas de Stadium.
        # Encerram somente o bloco atual do herói.
        if mode == "Stadium" and normalized_line in CATEGORY_HEADERS:
            save_current()

            current_hero = None
            current_lines = []
            continue

        # Fim da seção de heróis.
        if normalized_line in END_HEADERS:
            save_current()

            current_hero = None
            current_lines = []
            active = False
            mode = None
            continue

        # Detecta o nome de um herói.
        hero = canonical_hero(line)

        if hero:
            save_current()

            current_hero = hero
            current_lines = []
            continue

        # Guarda o texto associado ao herói atual.
        if current_hero:
            current_lines.append(line)

    save_current()

    return blocks


def main():
    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            "archive.json não encontrado na raiz do repositório."
        )

    database = json.loads(
        INPUT_FILE.read_text(encoding="utf-8")
    )

    records = []
    seen = set()

    for archive in database.get("archives", []):
        source_url = archive.get("url", "")
        month_text = archive.get("text", "")

        for article in split_articles(month_text):
            for block in extract_hero_blocks(article):
                hero = block["hero"]
                mode = block["mode"]
                raw_text = block["raw_text"]

                if not raw_text:
                    continue

                key = (
                    hero,
                    mode,
                    article.get("date"),
                    article.get("title"),
                    raw_text
                )

                if key in seen:
                    continue

                seen.add(key)

                records.append({
                    "hero": hero,
                    "hero_id": normalize(hero),
                    "mode": mode,
                    "date": article.get("date"),
                    "patch_title": article.get("title"),
                    "source": source_url,
                    "raw_text": raw_text,
                    "value_changes": extract_value_changes(raw_text),
                    "category": "hero_update"
                })

    # Ordena os registros por data e herói.
    records.sort(
        key=lambda item: (
            item.get("date") or "",
            item.get("hero") or "",
            item.get("mode") or ""
        )
    )

    overwatch_count = sum(
        1 for record in records
        if record["mode"] == "Overwatch"
    )

    stadium_count = sum(
        1 for record in records
        if record["mode"] == "Stadium"
    )

    result = {
        "source": "Blizzard official Overwatch patch notes",
        "generated_at": date.today().isoformat(),
        "total_records": len(records),
        "total_overwatch_records": overwatch_count,
        "total_stadium_records": stadium_count,
        "records": records
    }

    OUTPUT_FILE.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    print(f"Total de registros: {len(records)}")
    print(f"Overwatch: {overwatch_count}")
    print(f"Stadium: {stadium_count}")
    print(f"Arquivo criado: {OUTPUT_FILE.resolve()}")

    counts = {}

    for record in records:
        key = (record["hero"], record["mode"])
        counts[key] = counts.get(key, 0) + 1

    print("\nRegistros por herói e modo:")

    for (hero, mode), count in sorted(counts.items()):
        print(f"{hero} | {mode}: {count}")


if __name__ == "__main__":
    main()
