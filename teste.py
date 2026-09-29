import requests
from bs4 import BeautifulSoup

url = "https://overwatch.blizzard.com/pt-br/heroes/ana/"

response = requests.get(
    url,
    headers={
        "User-Agent": "Mozilla/5.0"
    },
    timeout=30
)

print("Status HTTP:", response.status_code)
print("Tamanho HTML:", len(response.text))

soup = BeautifulSoup(response.text, "html.parser")

print("Título:", soup.title.get_text(strip=True) if soup.title else "Não encontrado")

for termo in ["Rifle Biótico", "Dardo Sonífero", "Poderes Estádio"]:
    print(f"{termo}: {termo in response.text}")

with open("teste_blizzard.html", "w", encoding="utf-8") as arquivo:
    arquivo.write(response.text)

print("HTML salvo em teste_blizzard.html")
