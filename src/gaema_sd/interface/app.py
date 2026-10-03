"""Aplicação WSGI da interface local de operação (escritório e campo simulado).

Segurança (o que existe e o que NÃO existe):
- escuta só em 127.0.0.1; recusa pedido cujo `Host` não seja o da própria máquina (contra DNS rebinding);
- sessão em cookie HttpOnly + SameSite=Strict, trocada no login; token CSRF em todo formulário e conferência de `Origin`;
- páginas sem JavaScript, sem recurso externo, com Content-Security-Policy restritiva e `no-store`;
- erros mostram "o que houve / como resolver" (sem traceback); texto de usuário é sempre escapado pelo Jinja2;
- NÃO há autenticação real: o login escolhe um usuário SINTÉTICO de teste. Não usar com dados reais nem fora do
  computador local.
Esta camada só apresenta: regras de negócio, acesso e auditoria ficam no `Nucleo`.
"""

from __future__ import annotations

import dataclasses
import hmac
import json
import logging
import re
import secrets
import urllib.parse
from dataclasses import dataclass, field
from datetime import datetime
from http.cookies import SimpleCookie
from pathlib import Path
from wsgiref.simple_server import WSGIRequestHandler, make_server

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

from ..acesso.politica import Acao, Ator, pode
from ..auditoria.trilha import sanear_texto
from ..backup.ancora import ler_ancora
from ..config import parametro
from ..dominio import entidades as E
from ..dominio.enums import Estado, FormatoRelatorio, Papel, VariavelCampo
from ..erros import (AcessoNegado, AuditoriaCorrompida, ConflitoAtualizacao, ConflitoIdempotencia, ErroGaema,
                     RegistroNaoEncontrado, TransicaoInvalida, ValidacaoFalhou)
from ..exportacao import painel as exportacao_painel
from ..nucleo import ESTADOS_COM_RELATORIO, ESTADOS_DE_COLETA, Nucleo
from ..validacao.entidades import validar
from ..validacao.unidades import PARA_CM, ler_numero
from . import linguagem as L
from .campo import DISPOSITIVO_ID, Campo
from .mapa import mapa_svg

log = logging.getLogger("gaema_sd.interface")

LIMITE_CORPO = 64 * 1024
MAX_SESSOES = 50
_UUID = r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
ROTULO_PAPEL = L.PAPEL
TEMAS = ("auto", "claro", "escuro")
VARIAVEIS_PRESENCA = (VariavelCampo.PLANTAS_INVASORAS, VariavelCampo.CUPINS_MONTICULO, VariavelCampo.EROSAO_LAMINAR,
                      VariavelCampo.SULCOS, VariavelCampo.RAVINAS, VariavelCampo.VOCOROCAS, VariavelCampo.SOLO_EXPOSTO)
ROTULO_VARIAVEL = {VariavelCampo.PLANTAS_INVASORAS: "Plantas invasoras", VariavelCampo.CUPINS_MONTICULO: "Cupinzeiros (montículos)",
                   VariavelCampo.EROSAO_LAMINAR: "Erosão laminar", VariavelCampo.SULCOS: "Sulcos de erosão",
                   VariavelCampo.RAVINAS: "Ravinas", VariavelCampo.VOCOROCAS: "Voçorocas", VariavelCampo.SOLO_EXPOSTO: "Solo exposto"}
UNIDADES_R = [("kpa", "kPa"), ("mpa", "MPa"), ("kgf/cm2", "kgf/cm²")]
TIPO_LEIGO = {"PontoAmostral": "Ponto amostral", "Observacao": "Observação", "MedicaoPenetracao": "Medição de penetração",
              "Evidencia": "Foto ou documento"}
DECISAO_LEIGA = {"MANTER_CENTRAL": "mantida a versão da central", "ACEITAR_DISPOSITIVO": "aceita a versão do aparelho"}
SITUACAO_FILA = {"PENDENTE": ("Esperando envio", "andamento"), "ENVIADO": ("Enviado", "ok"),
                 "CONFLITO": ("Conflito: aguardando o coordenador", "critico"), "REJEITADO": ("Recusado", "atencao")}
# Usuários SINTÉTICOS de teste (os mesmos da demonstração, mais o administrador). Não são pessoas.
USUARIOS_DE_TESTE: dict[str, Ator] = {
    "analista": Ator.de("analista-sintetico", Papel.ANALISTA_TRIAGEM),
    "coord": Ator.de("coordenador-sintetico", Papel.COORDENADOR),
    "tecnico": Ator.de("tecnico-sintetico", Papel.TECNICO_CAMPO),
    "revisor": Ator.de("revisor-sintetico", Papel.REVISOR_TECNICO),
    "membro": Ator.de("membro-mp-sintetico", Papel.MEMBRO_MP),
    "auditor": Ator.de("auditor-sintetico", Papel.AUDITOR),
    "admin": Ator.de("administrador-sintetico", Papel.ADMINISTRADOR),
}
MENU = [("/painel", "Início", "inicio", None), ("/campo", "Campo", "campo", None),
        ("/conflitos", "Conflitos", "conflito", Acao.RESOLVER_CONFLITO_SINCRONIZACAO),
        ("/auditoria", "Auditoria", "auditoria", Acao.VERIFICAR_AUDITORIA), ("/exportar", "Exportar", "exportar", Acao.EXPORTAR),
        ("/backup", "Backup", "backup", Acao.GERIR_BACKUP), ("/ajuda", "Ajuda e limites", "ajuda", None)]


@dataclass
class Sessao:
    sid: str
    csrf: str = field(default_factory=lambda: secrets.token_hex(16))
    usuario: str | None = None
    tema: str = "auto"
    avisos: list = field(default_factory=list)   # ("ok", texto) | ("erro", Mensagem); mostrados uma vez


@dataclass
class Resposta:
    status: int = 200
    corpo: bytes = b""
    tipo: str = "text/html; charset=utf-8"
    cabecalhos: list[tuple[str, str]] = field(default_factory=list)
    cookie: str | None = None


_FRASES = {200: "OK", 303: "See Other", 400: "Bad Request", 403: "Forbidden", 404: "Not Found", 405: "Method Not Allowed",
           409: "Conflict", 413: "Payload Too Large", 422: "Unprocessable Entity", 500: "Internal Server Error"}


class Aplicacao:
    def __init__(self, nucleo: Nucleo, *, hosts_permitidos: set[str], usuarios: dict[str, Ator] | None = None,
                 campo: Campo | None = None):
        if nucleo.modo != "central":
            raise ErroGaema("a interface opera a instalação central (Nucleo em modo 'central')")
        self.nucleo = nucleo
        self.campo = campo
        self.hosts = {h.lower() for h in hosts_permitidos}
        self.usuarios = usuarios or USUARIOS_DE_TESTE
        self.sessoes: dict[str, Sessao] = {}
        self.env = Environment(loader=FileSystemLoader(str(Path(__file__).parent / "modelos")),
                               autoescape=select_autoescape(["j2"], default=True), undefined=StrictUndefined)
        self.env.globals.update(L=L)
        self.rotas = [
            ("GET", r"/", self.inicio), ("GET", r"/entrar", self.entrar_pagina), ("POST", r"/entrar", self.entrar),
            ("POST", r"/sair", self.sair), ("POST", r"/tema", self.tema), ("GET", r"/painel", self.painel),
            ("GET", r"/ajuda", self.ajuda),
            ("GET", rf"/demanda/({_UUID})", self.demanda), ("POST", rf"/demanda/({_UUID})/transitar", self.transitar),
            ("POST", rf"/demanda/({_UUID})/relatorio", self.emitir_relatorio), ("GET", rf"/relatorio/({_UUID})", self.relatorio),
            ("GET", r"/conflitos", self.conflitos), ("GET", rf"/conflitos/({_UUID})", self.conflito),
            ("POST", rf"/conflitos/({_UUID})/resolver", self.resolver),
            ("GET", r"/auditoria", self.auditoria), ("POST", r"/auditoria/verificar", self.verificar_auditoria),
            ("POST", r"/auditoria/ancora", self.gerar_ancora),
            ("GET", r"/exportar", self.exportar_pagina), ("POST", r"/exportar", self.exportar),
            ("GET", r"/backup", self.backup), ("POST", r"/backup/criar", self.backup_criar),
            ("POST", r"/backup/verificar", self.backup_verificar),
            ("GET", r"/campo", self.campo_pagina), ("POST", r"/campo/sincronizar", self.campo_sincronizar),
            ("POST", r"/campo/rede", self.campo_rede), ("POST", r"/campo/reenfileirar", self.campo_reenfileirar),
            ("GET", r"/campo/coleta", self.coleta), ("POST", r"/campo/coleta/ponto", self.coleta_ponto),
            ("POST", r"/campo/coleta/visto", self.coleta_visto), ("POST", r"/campo/coleta/medicao", self.coleta_medicao),
            ("POST", r"/campo/coleta/desfazer", self.coleta_desfazer), ("POST", r"/campo/coleta/salvar", self.coleta_salvar),
            ("POST", r"/campo/coleta/descartar", self.coleta_descartar),
            ("POST", r"/campo/coleta/conferir", self.coleta_conferir),
        ]
        self._livres = {self.entrar_pagina, self.entrar, self.tema}

    # ------------------------------------------------------------ WSGI

    def __call__(self, environ, start_response):
        try:
            r = self._despachar(environ)
        except Exception as e:  # noqa: BLE001 - nunca vaza detalhe interno ao navegador
            log.error("erro interno (%s)", type(e).__name__)
            r = self._erro(500, "Erro interno. Nada foi gravado pela metade; tente de novo ou chame a equipe técnica.")
        cab = [("Content-Type", r.tipo), ("Content-Length", str(len(r.corpo))), *self._cabecalhos_comuns(), *r.cabecalhos]
        if r.cookie:
            cab.append(("Set-Cookie", r.cookie))
        start_response(f"{r.status} {_FRASES.get(r.status, 'OK')}", cab)
        return [r.corpo]

    @staticmethod
    def _cabecalhos_comuns():
        return [
            ("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'; img-src data:; form-action 'self'; "
                                        "base-uri 'none'; frame-ancestors 'none'"),
            ("X-Content-Type-Options", "nosniff"), ("X-Frame-Options", "DENY"), ("Referrer-Policy", "no-referrer"),
            ("Cache-Control", "no-store"), ("Cross-Origin-Opener-Policy", "same-origin"),
        ]

    def _despachar(self, environ) -> Resposta:
        host = (environ.get("HTTP_HOST") or "").lower()
        if host not in self.hosts:
            return self._erro(400, "Endereço não permitido. Esta interface só atende neste computador.")
        metodo, caminho = environ["REQUEST_METHOD"].upper(), environ.get("PATH_INFO", "/")
        achou_caminho = False
        for m, padrao, funcao in self.rotas:
            achou = re.fullmatch(padrao, caminho)
            if not achou:
                continue
            achou_caminho = True
            if m != metodo:
                continue
            sessao = self._sessao(environ)
            form: dict[str, str] = {}
            if metodo == "POST":
                recusa = self._conferir_origem(environ, host)
                if recusa:
                    return recusa
                corpo = self._ler_corpo(environ)
                if isinstance(corpo, Resposta):
                    return corpo
                form = {k: v[0] for k, v in urllib.parse.parse_qs(corpo, keep_blank_values=True).items()}
                if funcao not in self._livres and not (sessao and sessao.usuario):
                    return self._ir("/entrar")
                if not sessao or not hmac.compare_digest(form.get("csrf", ""), sessao.csrf):
                    return self._erro(403, "Pedido recusado: o token de segurança da página expirou ou não confere.",
                                      "Volte, recarregue a página e tente de novo.")
            else:
                form = {k: v[0] for k, v in urllib.parse.parse_qs(environ.get("QUERY_STRING", ""),
                                                                  keep_blank_values=True).items()}
            ator = self.usuarios.get(sessao.usuario) if sessao and sessao.usuario else None
            if funcao not in self._livres and ator is None:
                return self._ir("/entrar")
            self._caminho = caminho
            resp = funcao(sessao, ator, form, *achou.groups())
            log.info("%s %s -> %s", metodo, re.sub(_UUID, "{id}", caminho), resp.status)
            return resp
        return self._erro(405 if achou_caminho else 404,
                          "Esta operação não existe nesta página." if achou_caminho else "Página não encontrada.")

    # ------------------------------------------------------------ sessão, origem, corpo

    def _sessao(self, environ) -> Sessao | None:
        c = SimpleCookie(environ.get("HTTP_COOKIE", ""))
        return self.sessoes.get(c["sid"].value) if "sid" in c else None

    def _nova_sessao(self, tema: str = "auto") -> Sessao:
        while len(self.sessoes) >= MAX_SESSOES:
            self.sessoes.pop(next(iter(self.sessoes)))
        s = Sessao(sid=secrets.token_hex(24), tema=tema)
        self.sessoes[s.sid] = s
        return s

    @staticmethod
    def _cookie(sid: str, *, apagar: bool = False) -> str:
        return f"sid={'' if apagar else sid}; HttpOnly; SameSite=Strict; Path=/" + ("; Max-Age=0" if apagar else "")

    def _conferir_origem(self, environ, host: str) -> Resposta | None:
        origem = environ.get("HTTP_ORIGIN")
        if origem is not None and origem.lower() != f"http://{host}":
            return self._erro(403, "Pedido recusado: veio de outra página que não esta interface.",
                              "Use os botões desta interface, aberta em 127.0.0.1.")
        return None

    def _ler_corpo(self, environ) -> str | Resposta:
        try:
            n = int(environ.get("CONTENT_LENGTH") or 0)
        except ValueError:
            return self._erro(400, "Pedido malformado.")
        if n < 0:
            return self._erro(400, "Pedido malformado.")
        if n > LIMITE_CORPO:
            return self._erro(413, "Pedido grande demais.", "Envie menos texto de uma vez.")
        tipo = (environ.get("CONTENT_TYPE") or "").split(";")[0].strip().lower()
        if n and tipo != "application/x-www-form-urlencoded":
            return self._erro(400, "Tipo de conteúdo não aceito.")
        return environ["wsgi.input"].read(n).decode("utf-8", errors="replace")

    # ------------------------------------------------------------ respostas

    def _menu(self, ator: Ator | None) -> list[dict]:
        if ator is None:
            return []
        itens = []
        for href, texto, icone, acao in MENU:
            permitido = acao is None or bool(ator and pode(ator, acao))
            razao = "" if permitido else f"seu papel ({L.papeis(ator.papeis)}) não tem esta permissão"
            itens.append({"href": href, "texto": texto, "icone": icone, "permitido": permitido, "razao": razao})
        return itens

    def _barra_campo(self, ator: Ator | None) -> dict | None:
        if self.campo and ator and pode(ator, Acao.COLETAR_CAMPO):
            return self.campo.status()
        return None

    def _pagina(self, nome: str, sessao: Sessao | None, ator: Ator | None, status: int = 200, **ctx) -> Resposta:
        avisos = sessao.avisos[:] if sessao else []
        if sessao:
            sessao.avisos.clear()
        permissoes = {a.name: bool(ator and pode(ator, a)) for a in Acao}
        html = self.env.get_template(nome + ".html.j2").render(
            sessao=sessao, ator=ator, avisos=avisos, permissoes=permissoes, tema=(sessao.tema if sessao else "auto"),
            menu=self._menu(ator), pagina_atual=getattr(self, "_caminho", ""), barra_campo=self._barra_campo(ator), **ctx)
        return Resposta(status, html.encode("utf-8"))

    def _erro(self, status: int, mensagem: str, como_resolver: str = "") -> Resposta:
        m = L.explicar(mensagem)
        if como_resolver or m.o_que_houve.startswith("Não foi possível"):
            m = L.Mensagem(mensagem, como_resolver or "Volte e tente de novo. Se continuar, chame a equipe técnica.", "")
        html = self.env.get_template("erro.html.j2").render(
            sessao=None, ator=None, avisos=[], permissoes={}, tema="auto", menu=[], pagina_atual="", barra_campo=None, m=m)
        return Resposta(status, html.encode("utf-8"))

    def _sem_permissao(self, e: Exception) -> Resposta:
        return self._erro(403, "Sem permissão: " + sanear_texto(str(e))[:300])

    @staticmethod
    def _ir(destino: str, cookie: str | None = None) -> Resposta:
        return Resposta(303, b"", cabecalhos=[("Location", destino)], cookie=cookie)

    @staticmethod
    def _aviso_erro(sessao: Sessao, texto: str) -> None:
        sessao.avisos.append(("erro", L.explicar(sanear_texto(texto)[:400])))

    def _executar(self, sessao: Sessao, voltar_para: str, fazer, sucesso: str) -> Resposta:
        """Roda uma ação do núcleo; sucesso ou falha viram aviso e redirecionamento (nada reenvia ao atualizar)."""
        try:
            extra = fazer()
            sessao.avisos.append(("ok", sucesso.format(extra=extra) if extra is not None else sucesso))
        except AcessoNegado as e:
            self._aviso_erro(sessao, "Sem permissão: " + str(e))
        except (TransicaoInvalida, ValidacaoFalhou, ConflitoAtualizacao, ConflitoIdempotencia, AuditoriaCorrompida,
                RegistroNaoEncontrado, ErroGaema) as e:
            self._aviso_erro(sessao, str(e))
        return self._ir(voltar_para)

    # ------------------------------------------------------------ entrada, tema

    def inicio(self, sessao, ator, form):
        return self._ir("/painel" if ator else "/entrar")

    def entrar_pagina(self, sessao, ator, form):
        anonima = sessao if sessao is not None else self._nova_sessao()
        usuarios = []
        for k, a in self.usuarios.items():
            sim, _ = L.pode_nao_pode(a)
            usuarios.append((k, L.papeis(a.papeis), a.id, ", ".join(sim[:4]) + ("…" if len(sim) > 4 else "") or "consultar"))
        r = self._pagina("entrar", anonima, None, usuarios=usuarios)
        if sessao is None:
            r.cookie = self._cookie(anonima.sid)
        return r

    def entrar(self, sessao, ator, form):
        escolhido = form.get("usuario", "")
        if sessao is None or escolhido not in self.usuarios:
            return self._erro(400, "Escolha um usuário de teste da lista.", "Volte à página de entrada e marque um dos usuários.")
        self.sessoes.pop(sessao.sid, None)                      # troca de sessão no login
        nova = self._nova_sessao(sessao.tema)
        nova.usuario = escolhido
        return self._ir("/painel", cookie=self._cookie(nova.sid))

    def sair(self, sessao, ator, form):
        self.sessoes.pop(sessao.sid, None)
        return self._ir("/entrar", cookie=self._cookie("", apagar=True))

    def tema(self, sessao, ator, form):
        if form.get("tema") in TEMAS:
            sessao.tema = form["tema"]
        return self._ir("/painel" if sessao.usuario else "/entrar")

    def ajuda(self, sessao, ator, form):
        return self._pagina("ajuda", sessao, ator)

    # ------------------------------------------------------------ escritório

    def painel(self, sessao, ator, form):
        demandas, sem_acesso = [], False
        try:
            demandas = [self.nucleo.resumo_demanda(ator, d.id) | {"titulo": d.titulo}
                        for d in self.nucleo.listar(ator, E.Demanda)]
        except AcessoNegado:
            sem_acesso = True
        contagem: dict[str, int] = {}
        for d in demandas:
            contagem[d["estado"]] = contagem.get(d["estado"], 0) + 1
        por_situacao = [(L.situacao(e).nome, L.situacao(e).tom, n) for e, n in sorted(contagem.items())]
        atencao = []
        if pode(ator, Acao.RESOLVER_CONFLITO_SINCRONIZACAO):
            n = len(self.nucleo.listar_conflitos(ator))
            if n:
                atencao.append({"tom": "erro", "icone": "critico", "titulo": f"{n} conflito(s) de sincronização aguardando sua decisão",
                                "texto": "Enquanto não decidir, a validação dos dados fica bloqueada.", "href": "/conflitos",
                                "link": "Abrir conflitos"})
        if self.campo and pode(ator, Acao.COLETAR_CAMPO):
            st = self.campo.status()
            if not st["conectado"]:
                atencao.append({"tom": "atencao", "icone": "rede-off", "titulo": "Aparelho sem rede (simulação)",
                                "texto": "A coleta continua salva no aparelho; sincronize quando a rede voltar.", "href": "/campo",
                                "link": "Ir ao Campo"})
            if st["pendentes"]:
                atencao.append({"tom": "info", "icone": "fila", "titulo": f"{st['pendentes']} registro(s) esperando envio",
                                "texto": "Sincronize o aparelho para enviá-los à central.", "href": "/campo", "link": "Ir ao Campo"})
            if st["problemas"]:
                atencao.append({"tom": "erro", "icone": "atencao", "titulo": f"{st['problemas']} registro(s) com problema no aparelho",
                                "texto": "Veja a fila do aparelho: há conflito ou recusa.", "href": "/campo", "link": "Ver a fila"})
        for d in demandas:
            if L.situacao(d["estado"]).tom in ("critico", "atencao"):
                atencao.append({"tom": "atencao", "icone": L.situacao(d["estado"]).tom,
                                "titulo": f"{d['titulo']}: {L.situacao(d['estado']).nome}",
                                "texto": L.situacao(d["estado"]).acao, "href": f"/demanda/{d['demanda_id']}", "link": "Abrir a demanda"})
        if atencao:
            proxima = "Resolva primeiro o que está em “Exige atenção”."
        elif demandas:
            proxima = "Abra uma demanda e siga a próxima ação indicada nela."
        elif sem_acesso:
            proxima = "Use as seções liberadas para o seu papel no menu."
        else:
            proxima = "Não há demandas neste banco."
        sim, nao = L.pode_nao_pode(ator)
        return self._pagina("painel", sessao, ator, demandas=demandas, sem_acesso=sem_acesso, por_situacao=por_situacao,
                            atencao=atencao, proxima=proxima, pode=sim, nao_pode=nao)

    def demanda(self, sessao, ator, form, demanda_id):
        try:
            d = self.nucleo.ler(ator, E.Demanda, demanda_id)
            resumo = self.nucleo.resumo_demanda(ator, demanda_id)
            transicoes = self.nucleo.transicoes_possiveis(ator, demanda_id)
            historico = self.nucleo.historico_de(ator, "Demanda", demanda_id, 20)
            relatorios = sorted((r for r in self.nucleo.listar(ator, E.Relatorio) if r.demanda_id == demanda_id),
                                key=lambda r: (r.formato.value, r.numero_versao))
            campanhas = {c.id for c in self.nucleo.listar(ator, E.CampanhaVistoria) if c.demanda_id == demanda_id}
            pontos_reg = [p for p in self.nucleo.listar(ator, E.PontoAmostral) if p.campanha_id in campanhas]
            area = self.nucleo.ler(ator, E.AreaInteresse, d.area_interesse_id) if d.area_interesse_id else None
        except AcessoNegado as e:
            return self._sem_permissao(e)
        except RegistroNaoEncontrado:
            return self._erro(404, "Demanda não encontrada.", "Volte ao início e abra a demanda pela lista.")
        for t in transicoes:
            t["papeis_leigos"] = L.papeis(Papel(p) for p in t["papeis"])
            t["bloqueio_leigo"] = L.explicar(t["bloqueio"]).o_que_houve + " " + L._trocar_codigos(t["bloqueio"]) if t["bloqueio"] else ""
        limite = parametro("gps_precisao_maxima_m")
        pontos = [{"codigo": p.codigo, "latitude": p.latitude, "longitude": p.longitude,
                   "precisao": f"{p.precisao_gps_m:g} m" if p.precisao_gps_m is not None else "não informada",
                   "gps_ruim": p.precisao_gps_m is not None and p.precisao_gps_m > limite}
                  for p in sorted(pontos_reg, key=lambda p: p.codigo)]
        selecionado = form.get("ponto") if form.get("ponto") in {p["codigo"] for p in pontos} else None
        svg, escala = mapa_svg(area.geometria_wkt if area else "", pontos, selecionado, f"Mapa esquemático: {d.titulo}")
        pode_emitir = pode(ator, Acao.EMITIR_RELATORIO) and d.estado in ESTADOS_COM_RELATORIO
        if not pode(ator, Acao.EMITIR_RELATORIO):
            razao = f"seu papel ({L.papeis(ator.papeis)}) não emite relatório; peça ao coordenador ou ao revisor técnico."
        elif d.estado not in ESTADOS_COM_RELATORIO:
            razao = "o relatório só é emitido depois do diagnóstico revisado."
        else:
            razao = ""
        return self._pagina("demanda", sessao, ator, d=d, resumo=resumo, transicoes=transicoes, historico=historico,
                            relatorios=relatorios, pode_emitir=pode_emitir, razao_emitir=razao,
                            formatos=[f.value for f in FormatoRelatorio], voce_age=any(t["disponivel"] for t in transicoes),
                            pontos=pontos, selecionado=selecionado, mapa=svg, escala=escala, limite_gps=f"{limite:g}")

    def transitar(self, sessao, ator, form, demanda_id):
        try:
            destino = Estado(form.get("destino", ""))
        except ValueError:
            return self._erro(400, "Destino desconhecido.", "Use um dos botões da página da demanda.")
        return self._executar(sessao, f"/demanda/{demanda_id}",
                              lambda: self.nucleo.transitar(ator, demanda_id, destino, motivo=form.get("motivo", "")) and None,
                              f"Demanda movida para: {L.situacao(destino).nome}.")

    def emitir_relatorio(self, sessao, ator, form, demanda_id):
        try:
            formato = FormatoRelatorio(form.get("formato", ""))
        except ValueError:
            return self._erro(400, "Formato desconhecido.", "Escolha HTML ou PDF.")

        def fazer():
            rel, _ = self.nucleo.emitir_relatorio(ator, demanda_id, formato, motivo_reemissao=form.get("motivo", ""))
            return rel.numero_versao
        return self._executar(sessao, f"/demanda/{demanda_id}", fazer, "Relatório emitido (versão {extra}).")

    def relatorio(self, sessao, ator, form, relatorio_id):
        try:
            conteudo, rel = self.nucleo.abrir_relatorio(ator, relatorio_id)
        except AcessoNegado as e:
            return self._sem_permissao(e)
        except (RegistroNaoEncontrado, ErroGaema) as e:
            return self._erro(404 if isinstance(e, RegistroNaoEncontrado) else 409, sanear_texto(str(e))[:300])
        pdf = rel.formato is FormatoRelatorio.PDF
        nome = f"relatorio-v{rel.numero_versao}.{rel.formato.value.lower()}"
        return Resposta(200, conteudo, "application/pdf" if pdf else "text/html; charset=utf-8",
                        [("Content-Disposition", f'{"attachment" if pdf else "inline"}; filename="{nome}"')])

    def conflitos(self, sessao, ator, form):
        try:
            lista = self.nucleo.listar_conflitos(ator, apenas_abertos=False)
        except AcessoNegado as e:
            return self._sem_permissao(e)
        for k in lista:
            k["tipo_leigo"] = TIPO_LEIGO.get(k["tipo"], k["tipo"])
            k["decisao_leiga"] = DECISAO_LEIGA.get(k["decisao"], k["decisao"])
            k["quando"] = k["criado_em"][:16].replace("T", " ")
        return self._pagina("conflitos", sessao, ator, conflitos=lista, abertos=sum(k["situacao"] == "ABERTO" for k in lista))

    def conflito(self, sessao, ator, form, conflito_id):
        try:
            k = self.nucleo.comparar_conflito(ator, conflito_id)
        except AcessoNegado as e:
            return self._sem_permissao(e)
        except RegistroNaoEncontrado:
            return self._erro(404, "Conflito não encontrado.", "Volte à lista de conflitos.")
        return self._pagina("conflito", sessao, ator, k=k, tipo_leigo=TIPO_LEIGO.get(k["tipo"], k["tipo"]),
                            decisao_leiga=DECISAO_LEIGA.get(k["decisao"], k["decisao"]))

    def resolver(self, sessao, ator, form, conflito_id):
        return self._executar(sessao, f"/conflitos/{conflito_id}",
                              lambda: self.nucleo.resolver_conflito_sincronizacao(
                                  ator, conflito_id, form.get("decisao", ""), form.get("motivo", "")),
                              "Decisão registrada. Agora mova a demanda de volta na página dela (o sistema não faz isso "
                              "sozinho). O aparelho recebe a decisão na próxima sincronização.")

    def auditoria(self, sessao, ator, form):
        try:
            eventos = list(reversed(self.nucleo.eventos_recentes(ator, 30)))
        except AcessoNegado as e:
            return self._sem_permissao(e)
        return self._pagina("auditoria", sessao, ator, eventos=eventos, total=len(self.nucleo.trilha.eventos))

    def verificar_auditoria(self, sessao, ator, form):
        ancora = None
        if form.get("ancora_arquivo", "").strip():
            try:
                ancora = ler_ancora(form["ancora_arquivo"].strip())
            except ErroGaema as e:
                self._aviso_erro(sessao, str(e))
                return self._ir("/auditoria")
        return self._executar(sessao, "/auditoria", lambda: self.nucleo.verificar_auditoria(ator, ancora),
                              "Trilha de auditoria íntegra: {extra} registros conferidos"
                              + (" (e conferidos com a âncora)." if ancora else "."))

    def gerar_ancora(self, sessao, ator, form):
        try:
            a = self.nucleo.gerar_ancora(ator)
        except (AcessoNegado, ErroGaema) as e:
            self._aviso_erro(sessao, str(e))
            return self._ir("/auditoria")
        return Resposta(200, json.dumps(a, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8"), "application/json",
                        [("Content-Disposition", f'attachment; filename="ancora-{a["eventos"]:08d}.json"')])

    def exportar_pagina(self, sessao, ator, form):
        return self._pagina("exportar", sessao, ator)

    def exportar(self, sessao, ator, form):
        try:
            pacote = self.nucleo.exportar_painel(ator)
        except AcessoNegado as e:
            self._aviso_erro(sessao, "Sem permissão: " + str(e))
            return self._ir("/exportar")
        return Resposta(200, exportacao_painel.serializar(pacote), "application/json",
                        [("Content-Disposition", 'attachment; filename="exportacao-gaema-sd.json"')])

    def backup(self, sessao, ator, form):
        try:
            nomes = self.nucleo.listar_backups(ator)
        except AcessoNegado as e:
            return self._sem_permissao(e)
        return self._pagina("backup", sessao, ator, backups=list(reversed(nomes)))

    def backup_criar(self, sessao, ator, form):
        return self._executar(sessao, "/backup", lambda: self.nucleo.criar_backup(ator)["nome"],
                              "Backup {extra} criado e verificado. Guarde uma cópia FORA deste computador.")

    def backup_verificar(self, sessao, ator, form):
        nome = form.get("nome", "")

        def fazer():
            problemas = self.nucleo.verificar_backup(ator, nome)
            if problemas:
                raise ErroGaema("o backup NÃO confere: " + "; ".join(problemas)[:350])
            return nome
        return self._executar(sessao, "/backup", fazer, "Backup {extra} confere.")

    # ------------------------------------------------------------ campo (aparelho simulado)

    def _missoes(self, ator) -> list[dict]:
        try:
            demandas = {d.id: d for d in self.nucleo.listar(ator, E.Demanda)}
            equipes = {e.id: e for e in self.nucleo.listar(ator, E.Equipe)}
            campanhas = self.nucleo.listar(ator, E.CampanhaVistoria)
        except AcessoNegado:
            return []
        saida = []
        for c in campanhas:
            d, eq = demandas.get(c.demanda_id), equipes.get(c.equipe_id)
            if d and eq and d.estado in ESTADOS_DE_COLETA and any(m.usuario_id == ator.id for m in eq.membros):
                saida.append({"id": c.id, "rotulo": f"{d.titulo} — {c.objetivo} ({c.data_planejada.strftime('%d/%m/%Y')})"})
        return saida

    def campo_pagina(self, sessao, ator, form):
        if not self.campo:
            return self._pagina("campo", sessao, ator, campo_ativo=False)
        st = self.campo.status()
        r = self.campo.rascunho()
        if r and pode(ator, Acao.COLETAR_CAMPO):
            proxima = f"Continue a coleta do ponto {r.get('codigo') or 'em andamento'} (etapa {r['etapa']} de 4)."
        elif st["problemas"]:
            proxima = "Veja os registros com problema na fila e avise o coordenador, se for conflito."
        elif st["pendentes"]:
            proxima = (f"Sincronize: {st['pendentes']} registro(s) esperando envio." if st["conectado"]
                       else f"Aguarde a rede voltar: {st['pendentes']} registro(s) seguem guardados no aparelho.")
        else:
            proxima = "Colete um novo ponto quando estiver no local."
        fila = []
        for situacao in ("CONFLITO", "REJEITADO", "PENDENTE", "ENVIADO"):
            for i in self.campo.dispositivo.fila.itens(situacao):
                rot, tom = SITUACAO_FILA[situacao]
                fila.append({"tipo_leigo": TIPO_LEIGO.get(i["tipo"], i["tipo"]), "situacao_leiga": rot, "tom": tom,
                             "tentativas": i["tentativas"], "obs": L.explicar(i["erro"]).o_que_houve if i["erro"] else ""})
        pode_reenfileirar = pode(ator, Acao.SINCRONIZAR) and any(
            not (i["erro"] or "").startswith("descartado:") for i in self.campo.dispositivo.fila.itens("REJEITADO"))
        return self._pagina("campo", sessao, ator, campo_ativo=True, proxima=proxima, rascunho=r, fila=fila[:40],
                            pode_reenfileirar=pode_reenfileirar)

    def _exigir_campo(self, ator, acao: Acao) -> str | None:
        if not self.campo:
            return "o aparelho simulado não está ligado nesta execução."
        if not pode(ator, acao):
            return f"seu papel ({L.papeis(ator.papeis)}) não pode fazer isso no aparelho."
        return None

    def campo_sincronizar(self, sessao, ator, form):
        razao = self._exigir_campo(ator, Acao.SINCRONIZAR)
        if razao:
            self._aviso_erro(sessao, "Sem permissão: " + razao)
            return self._ir("/campo")
        r = self.campo.sincronizador.rodada()
        env, rec = r.envio, r.reconciliacao
        partes = [f"{env.enviados} enviado(s)", f"{env.conflitos} conflito(s)", f"{env.rejeitados} recusado(s)"]
        if rec.aplicadas:
            partes.append(f"{rec.aplicadas} decisão(ões) do coordenador recebida(s)")
        if env.retidos:
            partes.append(f"{env.retidos} aguardando decisão de conflito")
        texto = ", ".join(partes) + "."
        agora = datetime.now().astimezone().strftime("%d/%m/%Y %H:%M")
        if env.interrompido or rec.interrompido:
            self.campo.ultimo_resultado = texto
            self._aviso_erro(sessao, f"sem rede: nada se perdeu; {env.pendentes_restantes} registro(s) continuam na fila. ({texto})")
        else:
            self.campo.ultima = f"{agora} — {texto}"
            sessao.avisos.append(("ok", f"Sincronização concluída: {texto}"))
        return self._ir("/campo")

    def campo_rede(self, sessao, ator, form):
        razao = self._exigir_campo(ator, Acao.SINCRONIZAR)
        if razao:
            self._aviso_erro(sessao, "Sem permissão: " + razao)
            return self._ir("/campo")
        self.campo.canal.fora_do_ar = not self.campo.canal.fora_do_ar
        sessao.avisos.append(("ok", "Simulação: rede " + ("desligada. A coleta continua salva no aparelho."
                                                          if self.campo.canal.fora_do_ar else "religada.")))
        return self._ir("/campo")

    def campo_reenfileirar(self, sessao, ator, form):
        razao = self._exigir_campo(ator, Acao.SINCRONIZAR)
        if razao:
            self._aviso_erro(sessao, "Sem permissão: " + razao)
            return self._ir("/campo")
        n = self.campo.sincronizador.reenfileirar_rejeitados()
        sessao.avisos.append(("ok", f"{n} registro(s) voltaram para a fila de envio."))
        return self._ir("/campo")

    # ---- coleta em etapas
    def _rascunho_ou_novo(self) -> dict:
        return self.campo.rascunho() or Campo.rascunho_novo()

    def _guarda_coleta(self, sessao, ator) -> Resposta | None:
        razao = self._exigir_campo(ator, Acao.COLETAR_CAMPO)
        if razao:
            self._aviso_erro(sessao, "Sem permissão: " + razao)
            return self._ir("/campo")
        return None

    def _ir_etapa(self, r: dict, etapa: int) -> Resposta:
        r["etapa"] = etapa
        r["max_etapa"] = max(r.get("max_etapa", 1), etapa)
        self.campo.salvar_rascunho(r)
        return self._ir("/campo/coleta")

    def coleta(self, sessao, ator, form):
        bloqueio = self._guarda_coleta(sessao, ator)
        if bloqueio:
            return bloqueio
        r = self._rascunho_ou_novo()
        pedida = form.get("etapa", "")
        if pedida.isdigit() and 1 <= int(pedida) <= r.get("max_etapa", 1):
            r["etapa"] = int(pedida)
            self.campo.salvar_rascunho(r)
        missoes = self._missoes(ator)
        rotulo = next((m["rotulo"] for m in missoes if m["id"] == r.get("missao")), "—")
        limite = parametro("gps_precisao_maxima_m")
        try:
            gps_ruim = float(str(r.get("precisao", "")).replace(",", ".")) > limite
        except ValueError:
            gps_ruim = False
        return self._pagina("coleta", sessao, ator, etapa=r["etapa"], r=r, missoes=missoes, missao_rotulo=rotulo,
                            variaveis=[(v.value, ROTULO_VARIAVEL[v]) for v in VARIAVEIS_PRESENCA],
                            unidades_p=list(PARA_CM), unidades_r=UNIDADES_R, limite_gps=f"{limite:g}", gps_ruim=gps_ruim,
                            rotulo_unidade=lambda u: dict(UNIDADES_R).get(u, u))

    def coleta_ponto(self, sessao, ator, form):
        bloqueio = self._guarda_coleta(sessao, ator)
        if bloqueio:
            return bloqueio
        r = self._rascunho_ou_novo()
        for k in ("missao", "codigo", "latitude", "longitude", "precisao", "capturado_em"):
            r[k] = form.get(k, "").strip()[:80]
        faltando = [n for k, n in (("missao", "vistoria"), ("codigo", "código do ponto"), ("latitude", "latitude"),
                                   ("longitude", "longitude"), ("precisao", "precisão do GPS"), ("capturado_em", "data e hora"))
                    if not r[k]]
        erros = []
        for k, nome, lim in (("latitude", "latitude", 90), ("longitude", "longitude", 180)):
            try:
                if r[k] and abs(ler_numero(r[k])) > lim:
                    erros.append(f"a {nome} deve estar entre -{lim} e {lim}")
            except ValueError:
                erros.append(f"a {nome} precisa ser um número (use vírgula ou ponto)")
        try:
            if r["precisao"] and ler_numero(r["precisao"]) <= 0:
                erros.append("a precisão do GPS precisa ser maior que zero")
        except ValueError:
            erros.append("a precisão do GPS precisa ser um número")
        if r["missao"] and r["missao"] not in {m["id"] for m in self._missoes(ator)}:
            erros.append("escolha uma vistoria da lista")
        self.campo.salvar_rascunho(r)                      # nada se perde, mesmo com erro
        if faltando or erros:
            texto = ("Falta preencher: " + ", ".join(faltando) + ". " if faltando else "") + "; ".join(erros)
            sessao.avisos.append(("erro", L.Mensagem("Alguns campos da etapa 1 precisam de ajuste.",
                                                     "Corrija o que está indicado e toque em “Salvar e seguir”.", texto.strip())))
            return self._ir("/campo/coleta")
        return self._ir_etapa(r, 2)

    def coleta_visto(self, sessao, ator, form):
        bloqueio = self._guarda_coleta(sessao, ator)
        if bloqueio:
            return bloqueio
        r = self._rascunho_ou_novo()
        r["presenca"] = {v.value: form.get(v.value, "nao_observado") if form.get(v.value) in ("sim", "nao", "nao_observado")
                         else "nao_observado" for v in VARIAVEIS_PRESENCA}
        r["hipotese"] = form.get("hipotese", "").strip()[:300]
        return self._ir_etapa(r, 3)

    def coleta_medicao(self, sessao, ator, form):
        bloqueio = self._guarda_coleta(sessao, ator)
        if bloqueio:
            return bloqueio
        r = self._rascunho_ou_novo()
        up, ur = form.get("unidade_p", ""), form.get("unidade_r", "")
        erros = []
        for campo_, nome in (("profundidade", "profundidade"), ("resistencia", "resistência")):
            try:
                if ler_numero(form.get(campo_, "")) < 0:
                    erros.append(f"a {nome} não pode ser negativa")
            except (TypeError, ValueError):
                erros.append(f"a {nome} precisa ser um número (use vírgula ou ponto)")
        if up not in PARA_CM or ur not in dict(UNIDADES_R):
            erros.append("escolha a unidade da lista")
        if erros:
            sessao.avisos.append(("erro", L.Mensagem("A repetição não foi anotada.", "Corrija o valor e anote de novo.",
                                                     "; ".join(erros))))
            return self._ir("/campo/coleta")
        r["medicoes"].append({"profundidade": form["profundidade"].strip(), "unidade_p": up, "resistencia": form["resistencia"].strip(),
                              "unidade_r": ur, "umidade": form.get("umidade", "").strip()[:120]})
        r["ultima_unidade_p"], r["ultima_unidade_r"], r["ultima_umidade"] = up, ur, form.get("umidade", "").strip()[:120]
        self.campo.salvar_rascunho(r)
        sessao.avisos.append(("ok", f"Repetição {len(r['medicoes'])} anotada no rascunho."))
        return self._ir("/campo/coleta")

    def coleta_conferir(self, sessao, ator, form):
        bloqueio = self._guarda_coleta(sessao, ator)
        if bloqueio:
            return bloqueio
        r = self._rascunho_ou_novo()
        if r.get("max_etapa", 1) < 3:
            self._aviso_erro(sessao, "complete as etapas anteriores antes da conferência.")
            return self._ir("/campo/coleta")
        return self._ir_etapa(r, 4)

    def coleta_desfazer(self, sessao, ator, form):
        bloqueio = self._guarda_coleta(sessao, ator)
        if bloqueio:
            return bloqueio
        r = self._rascunho_ou_novo()
        if r["medicoes"]:
            r["medicoes"].pop()
            self.campo.salvar_rascunho(r)
            sessao.avisos.append(("ok", "Última repetição desfeita."))
        return self._ir("/campo/coleta")

    def coleta_descartar(self, sessao, ator, form):
        bloqueio = self._guarda_coleta(sessao, ator)
        if bloqueio:
            return bloqueio
        self.campo.descartar_rascunho()
        sessao.avisos.append(("ok", "Rascunho descartado. Nada foi salvo no aparelho."))
        return self._ir("/campo")

    def coleta_salvar(self, sessao, ator, form):
        bloqueio = self._guarda_coleta(sessao, ator)
        if bloqueio:
            return bloqueio
        r = self.campo.rascunho()
        if not r or r.get("max_etapa", 1) < 4:
            self._aviso_erro(sessao, "a coleta ainda não passou por todas as etapas.")
            return self._ir("/campo/coleta")
        try:
            quando = datetime.fromisoformat(r["capturado_em"]).astimezone()
            base = dict(sintetico=True)
            chave = f"{DISPOSITIVO_ID}:{r['missao'][:8]}:{r['codigo']}"
            ponto = E.PontoAmostral(campanha_id=r["missao"], codigo=r["codigo"], latitude=ler_numero(r["latitude"]),
                                    longitude=ler_numero(r["longitude"]), precisao_gps_m=ler_numero(r["precisao"]),
                                    capturado_em=quando, dispositivo_id=DISPOSITIVO_ID, chave_idempotencia=chave, **base)
            registros = [ponto]
            for v in VARIAVEIS_PRESENCA:
                val = r["presenca"].get(v.value)
                if val in ("sim", "nao"):
                    registros.append(E.Observacao(ponto_id=ponto.id, variavel=v, valor_bruto="sim" if val == "sim" else "não",
                                                  unidade_bruta="presenca", observado_em=quando, observador_id=ator.id,
                                                  chave_idempotencia=f"{chave}:obs:{v.value}", **base))
            if r.get("hipotese"):
                registros.append(E.Observacao(ponto_id=ponto.id, variavel=VariavelCampo.HIPOTESE_ALTERNATIVA,
                                              valor_bruto=r["hipotese"], unidade_bruta="texto", observado_em=quando,
                                              observador_id=ator.id, chave_idempotencia=f"{chave}:obs:hip", **base))
            for i, m in enumerate(r["medicoes"], 1):
                registros.append(E.MedicaoPenetracao(ponto_id=ponto.id, repeticao=i, profundidade_bruta=m["profundidade"],
                                                     profundidade_unidade=m["unidade_p"], resistencia_bruta=m["resistencia"],
                                                     resistencia_unidade=m["unidade_r"], contexto_umidade=m["umidade"],
                                                     medido_em=quando, chave_idempotencia=f"{chave}:pen:{i}", **base))
        except (ValueError, KeyError) as e:
            self._aviso_erro(sessao, f"dados do rascunho incompletos ou inválidos ({type(e).__name__}); volte às etapas.")
            return self._ir("/campo/coleta")
        problemas = [f"{p.campo}: {p.mensagem}" for reg in registros
                     for p in validar(dataclasses_replace_autoria(reg, ator)) if p.gravidade.value == "ERRO"]
        if problemas:
            sessao.avisos.append(("erro", L.Mensagem("A conferência achou dados que o sistema não aceita.",
                                                     "Volte à etapa indicada, corrija e salve de novo.", "; ".join(problemas)[:400])))
            return self._ir("/campo/coleta")
        try:
            for reg in registros:
                self.campo.dispositivo.coletar(reg)
        except ErroGaema as e:
            self._aviso_erro(sessao, str(e))
            return self._ir("/campo/coleta")
        self.campo.descartar_rascunho()
        st = self.campo.status()
        n_obs = sum(isinstance(x, E.Observacao) for x in registros)
        n_med = sum(isinstance(x, E.MedicaoPenetracao) for x in registros)
        sessao.avisos.append(("ok", f"Ponto {ponto.codigo} salvo no aparelho: {n_obs} observação(ões) e {n_med} medição(ões). "
                                    f"Na fila: {st['pendentes']}. Sincronize quando houver rede."))
        return self._ir("/campo")


def dataclasses_replace_autoria(reg, ator):
    """Para pré-validar como o núcleo validará: a autoria é preenchida com o usuário logado."""
    return dataclasses.replace(reg, criado_por=ator.id)


class _Silencioso(WSGIRequestHandler):
    def log_message(self, formato, *args):   # o log de acesso padrão mostraria caminhos; usamos o logger da aplicação
        pass


def servir(nucleo: Nucleo, porta: int = 8765, *, usuarios: dict[str, Ator] | None = None, campo: Campo | None = None):
    """Cria o servidor em 127.0.0.1 (nunca em outra interface). O chamador chama `serve_forever()`."""
    hosts = {f"127.0.0.1:{porta}", f"localhost:{porta}"}
    servidor = make_server("127.0.0.1", porta, Aplicacao(nucleo, hosts_permitidos=hosts, usuarios=usuarios, campo=campo),
                           handler_class=_Silencioso)
    if porta == 0:   # porta escolhida pelo sistema (testes): ajusta os hosts permitidos
        real = servidor.server_address[1]
        servidor.get_app().hosts = {f"127.0.0.1:{real}", f"localhost:{real}"}
    return servidor
