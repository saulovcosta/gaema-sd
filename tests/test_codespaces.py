"""Teste pelo navegador no GitHub Codespaces (DEC-029): a interface continua escutando só em 127.0.0.1 e aceita o
endereço encaminhado pelo Codespaces SÓ quando as variáveis do próprio Codespace existem. Só dados sintéticos."""

import http.client
import json
import shutil
import socket
import subprocess
import threading
import urllib.parse
from pathlib import Path

import pytest

from gaema_sd.interface import servir
from gaema_sd.interface.app import hosts_codespaces
from gaema_sd.nucleo import Nucleo
from gaema_sd.persistencia import Repositorio

from .test_interface import Cliente, modelo  # noqa: F401 - fixture reaproveitada

RAIZ = Path(__file__).resolve().parents[1]
AMBIENTE = {"CODESPACES": "true", "CODESPACE_NAME": "glowing-spork-6v544q9px99r2gvg",
            "GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN": "app.github.dev"}


def test_devcontainer_python_312_dependencias_porta_e_inicio():
    d = json.loads((RAIZ / ".devcontainer" / "devcontainer.json").read_text(encoding="utf-8"))
    assert "python:1-3.12" in d["image"]
    assert "pip install -r requirements-dev.txt" in d["postCreateCommand"]
    assert d["postAttachCommand"] == "scripts/interface.sh"
    assert d["forwardPorts"] == [8765] and d["portsAttributes"]["8765"]["onAutoForward"] == "openBrowser"
    assert d["portsAttributes"]["8765"]["visibility"] == "private"     # só o dono do Codespace acessa


def test_endereco_encaminhado_so_dentro_do_codespaces():
    assert hosts_codespaces(8765, {}) == set()
    assert hosts_codespaces(8765, {**AMBIENTE, "CODESPACES": "false"}) == set()
    assert hosts_codespaces(8765, AMBIENTE) == {"glowing-spork-6v544q9px99r2gvg-8765.app.github.dev"}
    for ruim in ({"CODESPACE_NAME": "x/../evil"}, {"CODESPACE_NAME": "evil.com:80#"},
                 {"GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN": "evil.com/"}, {"CODESPACE_NAME": ""},
                 {"GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN": ""}):
        assert hosts_codespaces(8765, {**AMBIENTE, **ruim}) == set(), ruim


@pytest.fixture
def servidor(modelo, tmp_path):
    """Servidor real em porta livre, criado como dentro de um Codespace; devolve (porta, endereço encaminhado)."""
    destino = tmp_path / "srv"
    shutil.copytree(modelo, destino)
    repo = Repositorio(str(destino / "gaema-demo.db"))
    srv = servir(Nucleo(repo, destino), 0, ambiente=AMBIENTE)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    porta = srv.server_address[1]
    yield srv, porta, f"glowing-spork-6v544q9px99r2gvg-{porta}.app.github.dev"
    srv.shutdown()
    t.join(10)
    srv.server_close()
    repo.fechar()


def _pedir(porta, metodo, caminho, host, cabecalhos=None, corpo=None):
    """Faz o que o encaminhamento do Codespaces faz: conecta em 127.0.0.1 dentro do contêiner, com o Host público."""
    c = http.client.HTTPConnection("127.0.0.1", porta, timeout=10)
    h = {"Host": host, **(cabecalhos or {})}
    if corpo is not None:
        h["Content-Type"] = "application/x-www-form-urlencoded"
    c.request(metodo, caminho, body=corpo, headers=h)
    r = c.getresponse()
    texto = r.read().decode("utf-8", "replace")
    c.close()
    return r, texto


def test_servidor_continua_so_em_127_0_0_1(servidor):
    srv, porta, _ = servidor
    assert srv.server_address[0] == "127.0.0.1"
    externo = socket.gethostbyname(socket.gethostname())
    if externo.startswith("127."):
        pytest.skip("máquina sem endereço de rede além do loopback")
    with pytest.raises(OSError):
        socket.create_connection((externo, porta), timeout=2)


def test_encaminhamento_do_codespaces_alcanca_a_interface_e_o_login_funciona(servidor):
    _, porta, fora = servidor
    r, texto = _pedir(porta, "GET", "/entrar", fora)
    assert r.status == 200 and "Entrar (usuário de teste)" in texto
    import re
    csrf = re.search(r'name="csrf" value="([0-9a-f]+)"', texto).group(1)
    cookie = r.getheader("Set-Cookie").split(";")[0]
    corpo = urllib.parse.urlencode({"csrf": csrf, "usuario": "coord"})
    r, _ = _pedir(porta, "POST", "/entrar", fora, {"Cookie": cookie, "Origin": f"https://{fora}"}, corpo)
    assert r.status == 303 and r.getheader("Location") == "/painel"
    nova = r.getheader("Set-Cookie").split(";")[0]
    r, texto = _pedir(porta, "GET", "/painel", fora, {"Cookie": nova})
    assert r.status == 200 and "Papel em teste: Coordenador" in texto


def test_codespaces_continua_recusando_outras_origens_e_enderecos(servidor):
    _, porta, fora = servidor
    r, texto = _pedir(porta, "GET", "/entrar", fora)
    import re
    csrf = re.search(r'name="csrf" value="([0-9a-f]+)"', texto).group(1)
    cookie = r.getheader("Set-Cookie").split(";")[0]
    corpo = urllib.parse.urlencode({"csrf": csrf, "usuario": "coord"})
    for origem in (f"http://{fora}", "https://outro-8765.app.github.dev", "null", "https://evil.example"):
        r, _ = _pedir(porta, "POST", "/entrar", fora, {"Cookie": cookie, "Origin": origem}, corpo)
        assert r.status == 403, origem
    for host in ("outro-codespace-8765.app.github.dev", f"glowing-spork-6v544q9px99r2gvg-9999.app.github.dev",
                 "evil.example"):
        assert _pedir(porta, "GET", "/entrar", host)[0].status == 400, host
    assert _pedir(porta, "GET", "/entrar", f"127.0.0.1:{porta}")[0].status == 200     # acesso local segue igual


def test_fora_do_codespaces_o_endereco_encaminhado_e_recusado(modelo, tmp_path):
    destino = tmp_path / "srv"
    shutil.copytree(modelo, destino)
    repo = Repositorio(str(destino / "gaema-demo.db"))
    srv = servir(Nucleo(repo, destino), 0, ambiente={})
    app = srv.get_app().app
    assert app.hosts == {f"127.0.0.1:{srv.server_address[1]}", f"localhost:{srv.server_address[1]}"}
    r = Cliente(app, host=f"glowing-spork-6v544q9px99r2gvg-{srv.server_address[1]}.app.github.dev").get("/entrar")
    assert r.status == 400
    srv.server_close()
    repo.fechar()


def test_interface_sh_nao_abre_duas_vezes_na_mesma_porta(servidor):
    _, porta, _ = servidor
    r = subprocess.run(["bash", str(RAIZ / "scripts" / "interface.sh"), str(porta)], capture_output=True, text=True,
                       timeout=60, cwd=RAIZ)
    assert r.returncode == 0 and "já está aberta" in r.stdout


# Caso real (05/10/2026, Codespace do usuário): o encaminhamento entrega Host = localhost:PORTA, o navegador manda
# Origin = https://<codespace>-PORTA.app.github.dev, e o login era recusado com "veio de outra página" (DEC-031).
def _login_com(porta, host, origem, extra=None):
    r, texto = _pedir(porta, "GET", "/entrar", host, extra)
    import re
    csrf = re.search(r'name="csrf" value="([0-9a-f]+)"', texto).group(1)
    cookie = r.getheader("Set-Cookie").split(";")[0]
    corpo = urllib.parse.urlencode({"csrf": csrf, "usuario": "coord"})
    return _pedir(porta, "POST", "/entrar", host, {"Cookie": cookie, "Origin": origem, **(extra or {})}, corpo)


def test_caso_real_host_local_com_origem_publica_do_codespace_e_aceito(servidor):
    _, porta, fora = servidor
    for host in (f"localhost:{porta}", f"127.0.0.1:{porta}"):
        r, _ = _login_com(porta, host, f"https://{fora}")
        assert r.status == 303 and r.getheader("Location") == "/painel", host       # redirecionamento relativo
        nova = r.getheader("Set-Cookie").split(";")[0]
        r, texto = _pedir(porta, "GET", "/painel", host, {"Cookie": nova})
        assert r.status == 200 and "Papel em teste: Coordenador" in texto


def test_caso_real_outras_origens_continuam_recusadas(servidor):
    _, porta, fora = servidor
    for origem in ("https://evil.example", "https://outro-codespace-8765.app.github.dev", "null",
                   f"http://{fora}", f"https://{fora}.evil.example"):
        r, texto = _login_com(porta, f"localhost:{porta}", origem)
        assert r.status == 403, origem
        assert "127.0.0.1" not in texto and "endereço do seu Codespace" in texto      # mensagem certa no Codespace


def test_cabecalhos_do_cliente_nao_ampliam_o_que_e_aceito(servidor):
    _, porta, fora = servidor
    # X-Forwarded-Host não abre endereço novo: o Host continua conferido contra a lista fechada
    r, _ = _pedir(porta, "GET", "/entrar", "evil.example", {"X-Forwarded-Host": fora})
    assert r.status == 400
    # nem a origem: o endereço aceito vem só das variáveis do GitHub
    r, _ = _login_com(porta, f"localhost:{porta}", "https://evil.example", {"X-Forwarded-Host": "evil.example"})
    assert r.status == 403


def test_cookie_secure_pelo_encaminhamento_com_host_local(servidor):
    _, porta, fora = servidor
    r, _ = _login_com(porta, f"localhost:{porta}", f"https://{fora}", {"X-Forwarded-Proto": "https"})
    assert r.status == 303 and "; Secure" in r.getheader("Set-Cookie")
    r, _ = _login_com(porta, f"localhost:{porta}", f"https://{fora}")            # sem a indicação: sem Secure, mas entra
    assert r.status == 303 and "Secure" not in r.getheader("Set-Cookie")


def test_textos_no_codespace_nao_falam_em_127_0_0_1(servidor):
    _, porta, fora = servidor
    _, texto = _pedir(porta, "GET", "/entrar", f"localhost:{porta}")
    assert "seu Codespace do GitHub" in texto and "(127.0.0.1)" not in texto
    _, texto = _pedir(porta, "GET", "/entrar", "evil.example")
    assert "endereço do seu Codespace" in texto


def test_fora_do_codespace_host_local_com_origem_publica_continua_recusado(modelo, tmp_path):
    destino = tmp_path / "srv"
    shutil.copytree(modelo, destino)
    repo = Repositorio(str(destino / "gaema-demo.db"))
    srv = servir(Nucleo(repo, destino), 0, ambiente={})
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    porta = srv.server_address[1]
    try:
        r, _ = _login_com(porta, f"localhost:{porta}", f"https://glowing-spork-6v544q9px99r2gvg-{porta}.app.github.dev")
        assert r.status == 403
        r, _ = _login_com(porta, f"localhost:{porta}", f"http://localhost:{porta}")
        assert r.status == 303 and "Secure" not in r.getheader("Set-Cookie")
        _, texto = _pedir(porta, "GET", "/entrar", f"localhost:{porta}")
        assert "só neste computador (127.0.0.1)" in texto
    finally:
        srv.shutdown()
        t.join(10)
        srv.server_close()
        repo.fechar()
