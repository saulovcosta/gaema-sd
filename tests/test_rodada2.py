"""Rodada 2: ambiente do ponto (altura do pasto, solo, geologia, chuva 48 h), fotos por ponto e botões de opção.

Dados sintéticos; aparelho e rede simulados. Sem faixa, limiar ou lista de solos inventada: só o que o técnico digita.
"""

import re

from gaema_sd.config import parametro
from gaema_sd.dominio import entidades as E
from gaema_sd.dominio.enums import VariavelCampo
from gaema_sd.interface import app as A

from .test_interface import Cliente, cliente, modelo, sistema  # noqa: F401  (fixtures)
from .test_interface_uso import _etapa1, com_campo  # noqa: F401  (fixtures)

PNG = b"\x89PNG\r\n\x1a\n" + b"foto sintetica de teste"
JPEG = b"\xff\xd8\xff\xe0" + b"foto sintetica jpeg"
PDF = b"%PDF-1.4\n" + b"documento sintetico"
FRONTEIRA = "----fronteira-sintetica-7f3a"


def multipart(campos: dict, arquivos: dict) -> tuple[bytes, str]:
    partes = []
    for k, v in campos.items():
        partes.append(f'--{FRONTEIRA}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode())
    for k, (nome, tipo, dados) in arquivos.items():
        partes.append(f'--{FRONTEIRA}\r\nContent-Disposition: form-data; name="{k}"; filename="{nome}"\r\n'
                      f"Content-Type: {tipo}\r\n\r\n".encode() + dados + b"\r\n")
    return b"".join(partes) + f"--{FRONTEIRA}--\r\n".encode(), f"multipart/form-data; boundary={FRONTEIRA}"


def enviar_foto(c, nome="ponto.png", tipo="image/png", dados=PNG, categoria="FOTO_SOLO", csrf=None, rota=A.ROTA_FOTO):
    corpo, ct = multipart({"csrf": c.csrf if csrf is None else csrf, "categoria": categoria}, {"foto": (nome, tipo, dados)})
    return c.pedir("POST", rota, corpo=corpo, tipo=ct)


def ate_etapa3(c, amb):
    _etapa1(c, amb)
    c.post("/campo/coleta/visto", {"PLANTAS_INVASORAS": "sim"})
    assert "Etapa 3 de 5" in c.get("/campo/coleta").texto


def concluir(c):
    c.post("/campo/coleta/conferir")
    c.post("/campo/coleta/salvar")


# ================= ambiente do ponto =================================================================================

def test_ambiente_do_ponto_chega_a_central_sem_faixa_nem_lista(com_campo):
    amb, app, campo = com_campo
    c = Cliente(app).entrar("tecnico")
    ate_etapa3(c, amb)
    t = c.get("/campo/coleta").texto
    for rotulo in ("Altura do pasto", "Tipo de solo", "Formação geológica", "Choveu nas últimas 48 horas?"):
        assert rotulo in t
    assert '<select id="solo"' not in t and '<select id="geologia"' not in t        # texto livre: sem lista inventada
    c.post("/campo/coleta/ambiente", {"altura": "0,35", "altura_unidade": "m", "solo": "Latossolo (sintético)",
                                      "solo_fonte": "mapa sintético A", "geologia": "Formação sintética B",
                                      "geologia_fonte": "", "chuva": "sim", "chuva_nota": "garoa (sintético)"})
    assert "Etapa 4 de 5" in c.get("/campo/coleta").texto
    concluir(c)
    conf_ok = c.get("/campo").texto
    assert "5 observação(ões)" in conf_ok and "0 foto(s)" in conf_ok
    c.post("/campo/sincronizar")
    obs = {o.variavel: o for o in amb.na_central(E.Observacao)}
    assert obs[VariavelCampo.ALTURA_PASTO].valor_bruto == "0,35" and obs[VariavelCampo.ALTURA_PASTO].unidade_bruta == "m"
    assert obs[VariavelCampo.TIPO_SOLO].valor_bruto == "Latossolo (sintético)"
    assert obs[VariavelCampo.TIPO_SOLO].nota == "fonte informada: mapa sintético A"
    assert obs[VariavelCampo.FORMACAO_GEOLOGICA].nota == ""
    assert obs[VariavelCampo.PRECIPITACAO_RECENTE].valor_bruto == "sim"


def test_ambiente_em_branco_ou_nao_observado_nao_gera_registro(com_campo):
    amb, app, campo = com_campo
    c = Cliente(app).entrar("tecnico")
    ate_etapa3(c, amb)
    c.post("/campo/coleta/ambiente", {"chuva": "nao_observado"})
    concluir(c)
    c.post("/campo/sincronizar")
    variaveis = {o.variavel for o in amb.na_central(E.Observacao)}
    assert not variaveis & {VariavelCampo.ALTURA_PASTO, VariavelCampo.TIPO_SOLO, VariavelCampo.FORMACAO_GEOLOGICA,
                            VariavelCampo.PRECIPITACAO_RECENTE}


def test_altura_invalida_nao_avanca_e_nada_se_perde(com_campo):
    amb, app, campo = com_campo
    c = Cliente(app).entrar("tecnico")
    ate_etapa3(c, amb)
    c.post("/campo/coleta/ambiente", {"altura": "alto", "altura_unidade": "cm", "solo": "Argiloso (sintético)"})
    t = c.get("/campo/coleta").texto
    assert "Etapa 3 de 5" in t and "altura do pasto precisa ser um número" in t and 'value="Argiloso (sintético)"' in t
    c.post("/campo/coleta/ambiente", {"altura": "-3", "altura_unidade": "cm"})
    assert "não pode ser negativa" in c.get("/campo/coleta").texto
    c.post("/campo/coleta/ambiente", {"altura": "3", "altura_unidade": "pés"})
    assert "unidade da altura" in c.get("/campo/coleta").texto


def test_chuva_aceita_so_sim_nao_ou_nao_observado(com_campo):
    amb, app, campo = com_campo
    c = Cliente(app).entrar("tecnico")
    ate_etapa3(c, amb)
    c.post("/campo/coleta/ambiente", {"chuva": "10mm"})
    assert campo.rascunho()["ambiente"]["chuva"] == "nao_observado"


# ================= fotos =============================================================================================

def test_parametros_de_foto_tem_proveniencia():
    import json
    from gaema_sd.config import CAMINHO_PADRAO as CAMINHO_PARAMETROS
    dados = json.loads(CAMINHO_PARAMETROS.read_text(encoding="utf-8"))
    for k in ("interface_foto_maximo_bytes", "interface_fotos_por_ponto"):
        assert dados[k]["proveniencia"] == "AUTORAL" and dados[k]["valor"] > 0


def test_foto_valida_vira_evidencia_na_central_depois_de_sincronizar(com_campo):
    amb, app, campo = com_campo
    c = Cliente(app).entrar("tecnico")
    ate_etapa3(c, amb)
    r = enviar_foto(c)
    assert r.status == 303
    t = c.get("/campo/coleta").texto
    assert "Foto 1 anexada ao rascunho" in t and "ponto.png" in t and "Retirar foto 1" in t
    enviar_foto(c, nome="pasto.jpg", tipo="image/jpeg", dados=JPEG, categoria="FOTO_PANORAMICA")
    assert len(campo.rascunho()["fotos"]) == 2
    c.post("/campo/coleta/ambiente", {})
    c.post("/campo/coleta/conferir")
    assert "ponto.png" in c.get("/campo/coleta").texto
    c.post("/campo/coleta/salvar")
    assert "e 2 foto(s)" in c.get("/campo").texto
    assert not any((campo.pasta / "fotos-rascunho").glob("*.*")), "arquivo do rascunho deveria sair depois de salvar"
    c.post("/campo/sincronizar")
    evs = amb.na_central(E.Evidencia)
    ponto = next(p for p in amb.na_central(E.PontoAmostral) if p.codigo == "P09")
    assert {e.nome_arquivo_original for e in evs} >= {"ponto.png", "pasto.jpg"}
    nossas = [e for e in evs if e.ponto_id == ponto.id]
    assert len(nossas) == 2 and all(e.registrado_por == amb.a["tecnico"].id for e in nossas)


def test_foto_repetida_e_limite_por_ponto(com_campo, monkeypatch):
    amb, app, campo = com_campo
    c = Cliente(app).entrar("tecnico")
    ate_etapa3(c, amb)
    enviar_foto(c)
    enviar_foto(c)
    assert "mesma foto já foi anexada" in c.get("/campo/coleta").texto
    monkeypatch.setattr(A, "parametro", lambda k: 1 if k == "interface_fotos_por_ponto" else parametro(k))
    enviar_foto(c, nome="outra.jpg", tipo="image/jpeg", dados=JPEG)
    assert "o máximo nesta interface de teste" in c.get("/campo/coleta").texto and len(campo.rascunho()["fotos"]) == 1


def test_retirar_foto_e_descartar_apagam_o_arquivo(com_campo):
    amb, app, campo = com_campo
    c = Cliente(app).entrar("tecnico")
    ate_etapa3(c, amb)
    enviar_foto(c)
    sha = campo.rascunho()["fotos"][0]["sha256"]
    assert len(list((campo.pasta / "fotos-rascunho").iterdir())) == 1
    c.post("/campo/coleta/foto/remover", {"sha256": sha})
    assert campo.rascunho()["fotos"] == [] and not list((campo.pasta / "fotos-rascunho").iterdir())
    enviar_foto(c)
    c.post("/campo/coleta/descartar")
    assert not list((campo.pasta / "fotos-rascunho").iterdir())


def test_png_falso_tipo_errado_e_pdf_sao_recusados(com_campo):
    amb, app, campo = com_campo
    c = Cliente(app).entrar("tecnico")
    ate_etapa3(c, amb)
    enviar_foto(c, dados=b"nao sou png")                                       # conteúdo não confere
    assert "A foto não foi aceita" in c.get("/campo/coleta").texto
    enviar_foto(c, tipo="image/jpeg")                                         # tipo declarado diverge
    assert "A foto não foi aceita" in c.get("/campo/coleta").texto
    enviar_foto(c, nome="ponto.jpg")                                          # extensão diverge
    assert "A foto não foi aceita" in c.get("/campo/coleta").texto
    enviar_foto(c, nome="laudo.pdf", tipo="application/pdf", dados=PDF)
    assert "só entra foto" in c.get("/campo/coleta").texto
    enviar_foto(c, categoria="QUALQUER")
    assert "tipo da foto" in c.get("/campo/coleta").texto
    assert campo.rascunho()["fotos"] == []


def test_nome_com_caminho_vira_so_o_nome_final(com_campo):
    amb, app, campo = com_campo
    c = Cliente(app).entrar("tecnico")
    ate_etapa3(c, amb)
    enviar_foto(c, nome="../../etc/ponto.png")
    enviar_foto(c, nome="C:\\\\pasta\\\\pasto.jpg", tipo="image/jpeg", dados=JPEG)
    nomes = [f["nome"] for f in campo.rascunho()["fotos"]]
    assert nomes == ["ponto.png", "pasto.jpg"]
    arquivos = [p.name for p in (campo.pasta / "fotos-rascunho").iterdir()]
    assert all(re.fullmatch(r"[0-9a-f]{64}\.(png|jpg)", a) for a in arquivos)


def test_foto_grande_demais_e_recusada_antes_de_ler(com_campo, monkeypatch):
    amb, app, campo = com_campo
    c = Cliente(app).entrar("tecnico")
    ate_etapa3(c, amb)
    monkeypatch.setattr(A, "limite_foto", lambda: 100)
    r = enviar_foto(c, dados=PNG + b"x" * 200)
    assert r.status == 413 and "Foto grande demais" in r.texto and campo.rascunho()["fotos"] == []


def test_multipart_so_na_rota_de_foto_e_com_token(com_campo):
    amb, app, campo = com_campo
    c = Cliente(app).entrar("tecnico")
    ate_etapa3(c, amb)
    r = enviar_foto(c, rota="/campo/coleta/ambiente")
    assert r.status == 400 and "Tipo de conteúdo não aceito" in r.texto
    r = enviar_foto(c, csrf="0" * 32)
    assert r.status == 403 and campo.rascunho()["fotos"] == []
    corpo, ct = multipart({"csrf": c.csrf, "categoria": "FOTO_SOLO"}, {"foto": ("a.png", "image/png", PNG)})
    corpo = corpo.replace(b'name="categoria"', b'name="csrf"')               # campo repetido
    assert c.pedir("POST", A.ROTA_FOTO, corpo=corpo, tipo=ct).status == 400
    assert c.pedir("POST", A.ROTA_FOTO, corpo=b"lixo", tipo="multipart/form-data; boundary=x").status in (400, 403)


def test_foto_exige_sessao_de_tecnico_e_etapa(com_campo):
    amb, app, campo = com_campo
    coord = Cliente(app).entrar("coord")
    assert enviar_foto(coord).status == 303 and campo.rascunho() is None
    c = Cliente(app).entrar("tecnico")
    _etapa1(c, amb)                                                           # ainda na etapa 2
    enviar_foto(c)
    assert "complete as etapas anteriores antes de anexar fotos" in c.get("/campo/coleta").texto


def test_limite_de_corpo_da_foto_vem_do_parametro():
    assert A.limite_foto() == int(parametro("interface_foto_maximo_bytes")) + A.LIMITE_CORPO


# ================= botões de opção e lista alternativa ao mapa =========================================================

def test_sim_nao_e_nao_observado_sao_caixas_de_44px_com_foco_e_marca(sistema):
    css = cliente(sistema, "coord").get("/painel").texto
    regra = re.search(r"\.opcoes label\.opcao \{([^}]*)\}", css).group(1)
    assert "min-width:44px" in regra and "border:" in regra
    assert re.search(r"\.opcoes label\.opcao:has\(input:checked\) \{[^}]*border-width:3px[^}]*font-weight:700", css)
    assert re.search(r"\.opcoes label\.opcao:focus-within \{[^}]*outline:3px solid", css)


def test_radios_da_coleta_ficam_dentro_do_rotulo_clicavel(com_campo):
    amb, app, campo = com_campo
    c = Cliente(app).entrar("tecnico")
    _etapa1(c, amb)
    t = c.get("/campo/coleta").texto
    assert re.search(r'<label for="[^"]+" class="opcao"><input type="radio"', t)
    assert not re.search(r'<input type="radio"[^>]*>\s*<label', t)


def test_lista_de_pontos_e_alternativa_ao_mapa_com_salto(sistema):
    c = cliente(sistema, "coord")
    did = sistema[1].repo.listar(E.Demanda)[0].id
    t = c.get(f"/demanda/{did}").texto
    assert "Lista de pontos (alternativa ao mapa)" in t
    assert re.search(r'<a [^>]*href="#lista-pontos"[^>]*>', t) and 'id="lista-pontos"' in t


# ================= contrastes "a revisar" (docs/acessibilidade-contraste.md) =========================================

def _tokens(bloco: str) -> dict:
    return dict(re.findall(r"--([a-z0-9-]+):(#[0-9a-fA-F]{6})", bloco))


def test_contrastes_do_mapa_revisados_a_mao():
    from pathlib import Path

    from .test_acessibilidade import razao_contraste
    base = (Path(A.__file__).parent / "modelos" / "base.html.j2").read_text(encoding="utf-8")
    claro = _tokens(base[:base.index("prefers-color-scheme: dark")])
    escuro = _tokens(base[base.index("prefers-color-scheme: dark"):base.index("/* mapa */") if "/* mapa */" in base else None])
    assert re.search(r"\.mapa text \{[^}]*fill:var\(--texto\)[^}]*paint-order:stroke; stroke:var\(--superficie\)", base)
    doc = (Path(__file__).parents[1] / "docs" / "acessibilidade-contraste.md").read_text(encoding="utf-8")
    pares = [("texto", "superficie", 4.5), ("texto", "mapa-area", 4.5), ("mapa-ponto", "superficie", 3),
             ("mapa-ponto", "mapa-area", 3), ("critico", "superficie", 3), ("critico", "mapa-area", 3),
             ("mapa-borda", "superficie", 3)]
    for cores in (claro, escuro):
        for a, b, minimo in pares:
            razao = razao_contraste(cores[a], cores[b])
            assert razao >= minimo, (a, b, razao)
            assert f"{razao:.2f}".replace(".", ",") in doc, (a, b, razao)          # documento bate com as cores atuais


def test_mapa_do_relatorio_nao_passa_da_largura_por_causa_da_borda():
    from pathlib import Path
    modelo = (Path(A.__file__).parents[1] / "relatorio" / "modelo.html.j2").read_text(encoding="utf-8")
    regra = re.search(r"figure svg \{([^}]*)\}", modelo).group(1)
    assert "width: 100%" in regra and "border:" in regra and "box-sizing: border-box" in regra
    assert "max-height: 150mm" in regra                                           # mapa maior da Rodada 1 continua
