
import json
import time
from datetime import date
from pathlib import Path

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://overwatch.blizzard.com/pt-br/news/patch-notes/live"
START_YEAR = 2016
START_MONTH = 5

OUTPUT_FILE = Path("archive.json")

session = requests.Session()
session.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (compatible; OverwatchArchives/1.0; "
        "+https://github.com)"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
})


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

    print(f"Consultando {url}")

    response = session.get(url, timeout=30)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    # Remove elementos que não fazem parte do conteúdo da página.
    for element in soup.select(
        "script, style, nav, header, footer, "
        "iframe, noscript"
    ):
        element.decompose()

    content = soup.find("main") or soup.find("article") or soup.body

    if content is None:
        raise ValueError("Não foi possível localizar o conteúdo da página.")

    text = content.get_text("\n", strip=True)

    if len(text) < 100:
        raise ValueError("A página retornou conteúdo vazio ou incompleto.")

    return {
        "year": year,
        "month": month,
        "url": url,
        "title": soup.title.get_text(strip=True) if soup.title else "",
        "text": text,
    }


def main():
    records = []
    failures = []

    for year, month in get_months():
        try:
            record = collect_month(year, month)
            records.append(record)
            print(f"OK: {year}-{month:02d}")

        except Exception as error:
            failures.append({
                "year": year,
                "month": month,
                "error": str(error),
            })
            print(f"ERRO: {year}-{month:02d}: {error}")

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

    print(f"\nArquivos mensais coletados: {len(records)}")
    print(f"Meses com falha: {len(failures)}")
    print(f"Resultado salvo em {OUTPUT_FILE.resolve()}")


if __name__ == "__main__":
    main()
