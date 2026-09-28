
import json
import re
import unicodedata
from pathlib import Path

INPUT_FILE = Path("archive.json")
OUTPUT_FILE = Path("changes.json")

# Nomes oficiais e algumas variações encontradas nas notas em português.
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

# Variações de nomes que aparecem em notas antigas.
ALIASES = {
    "McCree": "Cassidy",
    "Soldier: 76": "Soldado: 76",
    "Soldier 76": "Soldado: 76",
    "Lúcio": "Lúcio",
    "Lucio": "Lúcio",
    "Torbjorn": "Torbjörn",
    "Wrecking Ball": "Wrecking Ball",
    "Life Weaver": "Lifeweaver",
}


def normalize(text):
    """Normaliza acentos, espaços e maiúsculas para comparar títulos."""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", text).strip().casefold()


HERO_LOOKUP = {}

for hero in HEROES:
    HERO_LOOKUP[normalize(hero)] = hero

for alias, canonical in ALIASES.items():
    HERO_LOOKUP[normalize(alias)] = canonical


def canonical_hero(line):
    """Retorna o nome oficial se a linha for exatamente um nome de herói."""
    return HERO_LOOKUP.get(normalize(line))


def clean_lines(text):
    return [
        line.strip()
        for line in text.splitlines()
        if line.strip()
    ]


def split_articles(text):
    """
    Divide o texto mensal em artigos usando títulos e datas
    das notas de atualização.
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
        r"^Notas de atualização de Overwatch",
        re.IGNORECASE
    )

    for line in lines:
        if date_pattern.match(line):
            if current:
                articles.append({
                    "date": current_date,
                    "title": current_title,
                    "lines": current
                })
            current = []
            current_date = line

        elif title_pattern.match(line):
            if current and current_title:
                articles.append({
                    "date": current_date,
                    "title": current_title,
                    "lines": current
                })
                current = []
            current_title = line
            current.append(line)

        elif current_title:
            current.append(line)

    if current:
        articles.append({
            "date": current_date,
            "title": current_title,
            "lines": current
        })

    return articles


def extract_value_changes(text):
    """Extrai pares de valores quando a nota usa de X para Y."""
    patterns = [
        r"(?:aumentad[oa]s?|reduzid[oa]s?|alterad[oa]s?)"
        r"\s+de\s+(.+?)\s+para\s+(.+?)(?:[.!;]|$)",

        r"(?:passou|passaram)\s+de\s+(.+?)\s+para\s+(.+?)(?:[.!;]|$)",

        r"(?:aumentad[oa]s?|reduzid[oa]s?)"
        r"\s+em\s+(.+?)(?:[.!;]|$)"
    ]

    results = []

    for line in text.splitlines():
        line = line.strip()

        for pattern in patterns:
            match = re.search(pattern, line, re.IGNORECASE)

            if not match:
                continue

            if len(match.groups()) == 2:
                results.append({
                    "old_value": match.group(1).strip(),
                    "new_value": match.group(2).strip(),
                    "text": line
                })
            else:
                results.append({
                    "old_value": None,
                    "new_value": None,
                    "text": line
                })

            break

    return results


def extract_hero_blocks(article):
    """
    Localiza seções de heróis dentro de um artigo.
    Guarda o bloco completo de cada herói para não perder contexto.
    """
    lines = article["lines"]
    blocks = []

    in_hero_section = False
    current_hero = None
    current_lines = []

    section_headers = {
        normalize("Atualizações dos heróis"),
        normalize("Atualizações de heróis"),
        normalize("Atualizações dos Heróis"),
        normalize("Atualizações dos heróis - Stadium"),
    }

    end_headers = {
        normalize("Correções de bugs"),
        normalize("Atualizações Gerais"),
        normalize("Atualizações gerais"),
        normalize("Mapas"),
        normalize("Geral"),
        normalize("Workshop"),
        normalize("Atualizações no Jogo Competitivo"),
        normalize("Atualizações Gerais"),
    }

    def save_current():
        if current_hero and current_lines:
            blocks.append({
                "hero": current_hero,
                "raw_text": "\n".join(current_lines)
            })

    for line in lines:
        normalized_line = normalize(line)

        if normalized_line in section_headers:
            save_current()
            current_hero = None
            current_lines = []
            in_hero_section = True
            continue

        if in_hero_section and normalized_line in end_headers:
            save_current()
            current_hero = None
            current_lines = []
            in_hero_section = False
            continue

        if not in_hero_section:
            continue

        hero = canonical_hero(line)

        if hero:
            save_current()
            current_hero = hero
            current_lines = []
            continue

        if current_hero:
            current_lines.append(line)

    save_current()
    return blocks


def main():
    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            "archive.json não encontrado na raiz do repositório."
        )

    database = json.loads(INPUT_FILE.read_text(encoding="utf-8"))

    records = []
    seen = set()

    for archive in database.get("archives", []):
        source_url = archive.get("url", "")
        month_text = archive.get("text", "")

        for article in split_articles(month_text):
            for block in extract_hero_blocks(article):
                hero = block["hero"]
                raw_text = block["raw_text"].strip()

                if not raw_text:
                    continue

                key = (
                    hero,
                    article.get("date"),
                    article.get("title"),
                    raw_text
                )

                if key in seen:
                    continue

                seen.add(key)

                value_changes = extract_value_changes(raw_text)

                records.append({
                    "hero": hero,
                    "date": article.get("date"),
                    "patch_title": article.get("title"),
                    "source": source_url,
                    "raw_text": raw_text,
                    "value_changes": value_changes,
                    "category": "hero_update"
                })

    records.sort(
        key=lambda item: (
            item.get("hero") or "",
            item.get("date") or ""
        )
    )

    result = {
        "source": "Blizzard official Overwatch patch notes",
        "generated_at": __import__("datetime").date.today().isoformat(),
        "total_records": len(records),
        "records": records
    }

    OUTPUT_FILE.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    print(f"Registros encontrados: {len(records)}")
    print(f"Arquivo criado: {OUTPUT_FILE.resolve()}")

    counts = {}

    for record in records:
        hero = record["hero"]
        counts[hero] = counts.get(hero, 0) + 1

    print("\nRegistros por herói:")

    for hero, count in sorted(counts.items()):
        print(f"{hero}: {count}")


if __name__ == "__main__":
    main()
