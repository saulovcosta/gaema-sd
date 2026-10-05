"""Rodada 1 (abrir de verdade): cookie Secure no Codespaces, cabeçalho Server sem versão, tabela da interface e CI."""

import re
from pathlib import Path

from .test_codespaces import _pedir, servidor  # noqa: F401 - fixture reaproveitada
from .test_interface import cliente, modelo, sistema  # noqa: F401 - fixtures reaproveitadas

RAIZ = Path(__file__).resolve().parents[1]


def _login(porta, host, origem):
    r, texto = _pedir(porta, "GET", "/entrar", host)
    csrf = re.search(r'name="csrf" value="([0-9a-f]+)"', texto).group(1)
    anonimo = r.getheader("Set-Cookie")
    cookie = anonimo.split(";")[0]
    r, _ = _pedir(porta, "POST", "/entrar", host, {"Cookie": cookie, "Origin": origem},
                  f"csrf={csrf}&usuario=coord")
    return anonimo, r


def test_cookie_secure_so_quando_o_acesso_vem_por_https_do_codespaces(servidor):
    _, porta, fora = servidor
    anonimo, r = _login(porta, fora, f"https://{fora}")
    assert r.status == 303 and "; Secure" in anonimo and "; Secure" in r.getheader("Set-Cookie")
    anonimo, r = _login(porta, f"127.0.0.1:{porta}", f"http://127.0.0.1:{porta}")
    assert r.status == 303 and "Secure" not in anonimo and "Secure" not in r.getheader("Set-Cookie")


def test_cookie_continua_httponly_e_samesite_strict(servidor):
    _, porta, fora = servidor
    _, r = _login(porta, fora, f"https://{fora}")
    c = r.getheader("Set-Cookie")
    assert "HttpOnly" in c and "SameSite=Strict" in c and "Path=/" in c


def test_cabecalho_server_sem_versao_do_python(servidor):
    _, porta, fora = servidor
    for host in (fora, f"127.0.0.1:{porta}", "evil.example"):       # inclusive na página de erro
        r, _ = _pedir(porta, "GET", "/entrar", host)
        assert r.getheader("Server") == "GAEMA-SD", (host, r.getheader("Server"))
        assert len(r.headers.get_all("Server")) == 1


def test_tabela_da_interface_nao_parte_cabecalho_nem_numero(sistema):
    t = cliente(sistema, "coord").get("/painel").texto
    assert ".tabela th { overflow-wrap:normal; }" in t
    assert "@media (min-width: 44.01rem) { .tabela td.num { white-space:nowrap; }" in t
    # selos descem para a linha de baixo e podem quebrar: a tabela de pontos cabe na coluna (medido no navegador)
    assert ".tabela td.num .etiqueta { display:flex; width:fit-content; max-width:100%; white-space:normal;" in t
    assert '.tabela th[scope="row"] .etiqueta { display:flex;' in t


def test_ci_roda_testes_e_auditoria_sem_segredos():
    y = (RAIZ / ".github" / "workflows" / "testes.yml").read_text(encoding="utf-8")
    assert re.search(r"^on:\n  push:\n  pull_request:", y, re.M)
    assert re.search(r"^permissions:\n  contents: read$", y, re.M)
    assert "secrets" not in y.lower() and "token" not in y.lower()
    assert "pip install -r requirements-dev.txt" in y and "python -m pytest" in y
    assert "pip-audit -r requirements-dev.txt" in y and 'python-version: "3.12"' in y
