
import json
import re
import time
from datetime import date
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://overwatch.blizzard.com/pt-br/news/patch-notes/live"
HEROES_URL = "https://overwatch.blizzard.com/pt-br/heroes/"

START_YEAR = 2016
START_MONTH = 5

OUTPUT_FILE = Path("archive.json")
HEROES_OUTPUT_FILE = Path("heroes_data.json")

session = requests.Session()
session.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (compatible; OverwatchArchives/1.0; "
        "+https://github.com)"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
})


def get_soup(url):
    response = session.get(url, timeout=30)
    response.raise_for_status()

    return BeautifulSoup(response.text, "html.parser")


# ============================================================
# COLETA DE PATCH NOTES - MANTIDA
# ============================================================

def get_months():
    today = date.today()
    months = []

    year = START_YEAR
    month = START_MONTH

    while (year, month) <= (today.year, today.month):
        months.append((year, month))

        month += 1
        if month == 13:
            month = 1
            year += 1

    return months


def collect_month(year, month):
    url = f"{BASE_URL}/{year}/{month:02d}/"

    print(f"Consultando patch notes: {url}")

    soup = get_soup(url)

    for element in soup.select(
        "script, style, nav, header, footer, "
        "iframe, noscript"
    ):
        element.decompose()

    content = soup.find("main") or soup.find("article") or soup.body

    if content is None:
        raise ValueError(
            "Não foi possível localizar o conteúdo da página."
        )

    text = content.get_text("\n", strip=True)

    if len(text) < 100:
        raise ValueError(
            "A página retornou conteúdo vazio ou incompleto."
        )

    return {
        "year": year,
        "month": month,
        "url": url,
        "title": soup.title.get_text(strip=True) if soup.title else "",
        "text": text,
    }


def collect_patches():
    records = []
    failures = []

    for year, month in get_months():
        try:
            record = collect_month(year, month)
            records.append(record)
            print(f"OK: patch notes {year}-{month:02d}")

        except Exception as error:
            failures.append({
                "year": year,
                "month": month,
                "error": str(error),
            })

            print(f"ERRO: patch notes {year}-{month:02d}: {error}")

        time.sleep(1)

    database = {
        "source": BASE_URL,
        "updated_at": date.today().isoformat(),
        "total_months": len(records),
        "failed_months": failures,
        "archives": records,
    }

    OUTPUT_FILE.write_text(
        json.dumps(database, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"\nPatch notes coletados: {len(records)}")
    print(f"Meses com falha: {len(failures)}")
    print(f"Resultado salvo em {OUTPUT_FILE.resolve()}")


# ============================================================
# COLETA DAS FICHAS OFICIAIS DOS HERÓIS
# ============================================================

def normalize(text):
    import unicodedata

    text = unicodedata.normalize("NFKD", str(text or ""))
    text = "".join(
        char for char in text
        if not unicodedata.combining(char)
    )

    return re.sub(r"\s+", " ", text).strip().casefold()


def clean_text(element):
    if element is None:
        return ""

    return re.sub(
        r"\s+", " ", element.get_text(" ", strip=True)
    ).strip()


def get_hero_links():
    """
    Descobre os links de heróis diretamente na página
    oficial, sem manter uma lista manual de URLs.
    """
    print(f"\nConsultando elenco oficial: {HEROES_URL}")

    soup = get_soup(HEROES_URL)

    links = {}

    for anchor in soup.select("a[href]"):
        href = anchor.get("href", "").strip()

        if not href:
            continue

        absolute_url = urljoin(HEROES_URL, href)
        parsed = urlparse(absolute_url)

        if parsed.netloc != "overwatch.blizzard.com":
            continue

        match = re.match(
            r"^/pt-br/heroes/([^/]+)/?$",
            parsed.path,
            re.IGNORECASE
        )

        if not match:
            continue

        slug = match.group(1)

        if normalize(slug) in {
            "heroes", "herois"
        }:
            continue

        links[slug] = (
            f"https://overwatch.blizzard.com"
            f"/pt-br/heroes/{slug}/"
        )

    if not links:
        raise ValueError(
            "Nenhum link individual de herói foi encontrado "
            "na página oficial. A estrutura pode ter mudado "
            "ou os links podem ser carregados por JavaScript."
        )

    return links


def extract_meta(soup, *selectors):
    for selector in selectors:
        element = soup.select_one(selector)

        if element:
            value = (
                element.get("content")
                or element.get("datetime")
                or clean_text(element)
            )

            if value:
                return value.strip()

    return ""


def extract_hero_name(soup, slug):
    """
    Tenta obter o nome a partir do título e dos metadados
    oficiais da página individual.
    """
    candidates = [
        extract_meta(soup, 'meta[property="og:title"]'),
        extract_meta(soup, 'meta[name="twitter:title"]'),
        clean_text(soup.find("h1")),
        clean_text(soup.title),
    ]

    for candidate in candidates:
        if not candidate:
            continue

        candidate = re.sub(
            r"\s*[-|–]\s*(Overwatch|Heróis|Heroes).*$",
            "",
            candidate,
            flags=re.IGNORECASE
        ).strip()

        candidate = re.sub(
            r"^(Heróis|Heroes)\s*[-|:]\s*",
            "",
            candidate,
            flags=re.IGNORECASE
        ).strip()

        if candidate:
            return candidate

    return slug.replace("-", " ").title()


def extract_hero_description(soup):
    return extract_meta(
        soup,
        'meta[property="og:description"]',
        'meta[name="description"]',
        'meta[name="twitter:description"]',
    )


def extract_role(soup):
    """
    Procura a função no texto visível da ficha.
    Não deduz a função a partir do nome do personagem.
    """
    text = normalize(soup.get_text(" ", strip=True))

    role_patterns = [
        (r"\btanque\b", "Tanque"),
        (r"\bdano\b", "Dano"),
        (r"\bsuporte\b", "Suporte"),
    ]

    for pattern, role in role_patterns:
        if re.search(pattern, text):
            return role

    return ""


def extract_abilities(soup):
    """
    Extrai nomes e descrições de habilidades de elementos
    semânticos comuns nas páginas oficiais.

    Evita cadastrar títulos genéricos como habilidades.
    """
    abilities = []
    seen = set()

    # A página pode apresentar habilidades em cartões,
    # seções ou elementos com nomes acessíveis.
    selectors = [
        "[class*='ability']",
        "[class*='Ability']",
        "[data-testid*='ability']",
        "[data-testid*='Ability']",
    ]

    elements = []

    for selector in selectors:
        elements.extend(soup.select(selector))

    for element in elements:
        name_element = element.select_one(
            "h2, h3, h4, "
            "[class*='title'], "
            "[class*='name'], "
            "[class*='Title'], "
            "[class*='Name']"
        )

        if name_element is None:
            continue

        name = clean_text(name_element)

        if not name or len(name) > 100:
            continue

        description_parts = []

        for child in element.select("p, [class*='description']"):
            description = clean_text(child)

            if (
                description
                and description != name
                and description not in description_parts
            ):
                description_parts.append(description)

        description = " ".join(description_parts).strip()

        if not description:
            continue

        key = normalize(name)

        if key in seen:
            continue

        seen.add(key)

        abilities.append({
            "name": name,
            "description": description,
        })

    return abilities


def collect_hero(slug, url):
    print(f"Consultando herói: {slug}")

    soup = get_soup(url)

    name = extract_hero_name(soup, slug)
    summary = extract_hero_description(soup)
    role = extract_role(soup)
    abilities = extract_abilities(soup)

    return {
        "id": slug,
        "name": name,
        "role": role,
        "summary": summary,
        "release": None,
        "abilities": abilities,
        "source": url,
        "collected_at": date.today().isoformat(),
        "status": {
            "name": bool(name),
            "role": bool(role),
            "summary": bool(summary),
            "abilities": bool(abilities),
            "release": False,
        },
    }


def collect_heroes():
    failures = []
    records = []

    try:
        hero_links = get_hero_links()
    except Exception as error:
        print(f"ERRO ao consultar elenco oficial: {error}")
        return

    print(f"\nHeróis descobertos: {len(hero_links)}")

    for slug, url in sorted(hero_links.items()):
        try:
            hero = collect_hero(slug, url)
            records.append(hero)

            print(
                f"OK: {hero['name']} | "
                f"habilidades encontradas: "
                f"{len(hero['abilities'])}"
            )

        except Exception as error:
            failures.append({
                "slug": slug,
                "url": url,
                "error": str(error),
            })

            print(f"ERRO: {slug}: {error}")

        time.sleep(0.5)

    database = {
        "source": HEROES_URL,
        "updated_at": date.today().isoformat(),
        "total_heroes": len(records),
        "failed_heroes": failures,
        "heroes": records,
    }

    HEROES_OUTPUT_FILE.write_text(
        json.dumps(database, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"\nFichas coletadas: {len(records)}")
    print(f"Heróis com falha: {len(failures)}")
    print(
        f"Resultado salvo em "
        f"{HEROES_OUTPUT_FILE.resolve()}"
    )


# ============================================================
# EXECUÇÃO
# ============================================================

def main():
    collect_patches()
    collect_heroes()


if __name__ == "__main__":
    main()
