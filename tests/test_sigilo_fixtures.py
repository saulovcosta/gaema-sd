"""Segurança básica: nenhum dado pessoal real, número de procedimento ou segredo versionado."""

import re
import subprocess
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]

PADROES = {
    "CPF": re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b"),
    "CNPJ": re.compile(r"\b\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\b"),
    "processo CNJ": re.compile(r"\b\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}\b"),
    "recibo CAR": re.compile(r"\b[A-Z]{2}-\d{7}-[0-9A-F]{32}\b"),
    "e-mail": re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]+\b"),
    "telefone": re.compile(r"\(?\b\d{2}\)?\s?9?\d{4}-\d{4}\b"),
    "chave privada": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "token atribuído": re.compile(r"(?i)(client_secret|api_key|token|senha|password)\s*[=:]\s*['\"]?[A-Za-z0-9_\-]{8,}"),
}
PASTAS = ["fixtures", "src", "tests", "schemas", "config", "adapters", "scripts"]
EXCECOES = {"noreply@anthropic.com"}


def _arquivos():
    for pasta in PASTAS:
        for p in (RAIZ / pasta).rglob("*"):
            if p.is_file() and p.suffix in {".py", ".json", ".md", ".sh", ".txt", ".csv", ".xlsx", ""}:
                yield p


def test_sem_dados_pessoais_ou_segredos():
    achados = []
    for arq in _arquivos():
        if arq.name == "test_sigilo_fixtures.py":
            continue
        texto = arq.read_text(encoding="utf-8", errors="ignore")
        for nome, rx in PADROES.items():
            for m in rx.finditer(texto):
                if m.group(0) not in EXCECOES:
                    achados.append((str(arq.relative_to(RAIZ)), nome, m.group(0)[:20]))
    assert achados == []


def test_padroes_detectam_exemplos_inventados():
    assert PADROES["CPF"].search("123.456.789-09")
    assert PADROES["processo CNJ"].search("0000001-23.2026.8.27.0001")
    assert PADROES["token atribuído"].search("ARCGIS_TOKEN = 'abcdEFGH1234'")


def test_env_ignorado_e_exemplo_sem_valores():
    ignorados = (RAIZ / ".gitignore").read_text()
    assert ".env" in ignorados and "*.db" in ignorados
    for linha in (RAIZ / ".env.example").read_text().splitlines():
        if linha.startswith("ARCGIS_"):
            assert linha.endswith("="), linha


def test_nenhum_env_ou_banco_rastreado_pelo_git():
    r = subprocess.run(["git", "ls-files"], cwd=RAIZ, capture_output=True, text=True, check=True)
    rastreados = r.stdout.splitlines()
    assert not [f for f in rastreados if f.endswith((".db", ".sqlite")) or Path(f).name == ".env"]


def test_fixtures_marcadas_como_sinteticas():
    import json

    dados = json.loads((RAIZ / "fixtures" / "sinteticos" / "cenario_basico.json").read_text(encoding="utf-8"))
    assert "SINTÉTICOS" in dados["_aviso"]
    assert all(r["sintetico"] for k, v in dados.items() if not k.startswith("_") for r in v)
