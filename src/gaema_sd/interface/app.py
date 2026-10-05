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
import io
import json
import logging
import os
import re
import secrets
import threading
import time
import urllib.parse
from dataclasses import dataclass, field
from datetime import date, datetime
from http.cookies import SimpleCookie
from pathlib import Path
from socketserver import ThreadingMixIn
from wsgiref.simple_server import WSGIRequestHandler, WSGIServer, make_server

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

from ..acesso.politica import Acao, Ator, pode
from ..auditoria.trilha import sanear_texto
from ..backup.ancora import interpretar_ancora
from ..config import parametro
from ..dominio import entidades as E
from ..dominio.enums import (CategoriaEvidencia, CriterioPriorizacao, Estado, FormatoRelatorio, ModoProtocolo, OrigemAlerta,
                             OrigemAreaInteresse, Papel, SituacaoPedidoAcesso, TipoFonte, VariavelCampo)
from ..erros import (AcessoNegado, AuditoriaCorrompida, ConflitoAtualizacao, ConflitoIdempotencia, ErroGaema,
                     RegistroNaoEncontrado, TransicaoInvalida, ValidacaoFalhou)
from ..exportacao import painel as exportacao_painel
from ..nucleo import ATOR_PEDIDO_ACESSO, ESTADOS_COM_RELATORIO, ESTADOS_DE_COLETA, Nucleo
from ..validacao.entidades import PAPEIS_NAO_PEDIVEIS
from ..validacao.entidades import validar
from ..validacao.anexos import validar_anexo
from ..validacao.unidades import PARA_CM, ler_numero
from . import linguagem as L
from .campo import DISPOSITIVO_ID, Campo
from .mapa import mapa_svg

log = logging.getLogger("gaema_sd.interface")

LIMITE_CORPO = 64 * 1024
ROTA_FOTO = "/campo/coleta/foto"     # única rota que aceita multipart/form-data (foto do ponto)
TOTAL_ETAPAS = 5
TIPOS_FOTO = ("image/jpeg", "image/png")
AMBIENTE_VAZIO = {"altura": "", "altura_unidade": "cm", "solo": "", "solo_fonte": "", "geologia": "",
                  "geologia_fonte": "", "chuva": "nao_observado", "chuva_nota": ""}


def limite_foto() -> int:
    """Corpo máximo do envio de foto: o tamanho máximo da foto mais uma folga para os campos do formulário."""
    return int(parametro("interface_foto_maximo_bytes")) + LIMITE_CORPO
MAX_SESSOES = 50
MAX_ANONIMAS = 20
SESSAO_TTL = 8 * 3600          # segundos sem uso até a sessão expirar (escolha de projeto, AUTORAL)
TEMPO_SOCKET = 15              # segundos: conexão parada não prende o servidor para sempre
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
        ("/backup", "Backup", "backup", Acao.GERIR_BACKUP), ("/acessos", "Acessos de teste", "pessoa", Acao.DECIDIR_ACESSO_TESTE),
        ("/ajuda", "Ajuda e limites", "ajuda", None)]


@dataclass
class Sessao:
    sid: str
    csrf: str = field(default_factory=lambda: secrets.token_hex(16))
    usuario: str | None = None
    tema: str = "auto"
    usada_em: float = field(default_factory=time.monotonic)
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
        self.hosts_https: set[str] = set()   # endereços encaminhados por HTTPS (Codespaces; ver hosts_codespaces)
        self.usuarios = usuarios or USUARIOS_DE_TESTE
        self.sessoes: dict[str, Sessao] = {}
        self.env = Environment(loader=FileSystemLoader(str(Path(__file__).parent / "modelos")),
                               autoescape=select_autoescape(["j2"], default=True), undefined=StrictUndefined)
        self.env.globals.update(L=L)
        self.rotas = [
            ("GET", r"/", self.inicio), ("GET", r"/entrar", self.entrar_pagina), ("POST", r"/entrar", self.entrar),
            ("POST", r"/sair", self.sair), ("POST", r"/tema", self.tema), ("GET", r"/painel", self.painel),
            ("GET", r"/ajuda", self.ajuda),
            ("GET", r"/demanda/nova", self.demanda_nova), ("POST", r"/demanda/nova", self.demanda_criar),
            ("POST", rf"/demanda/({_UUID})/equipe", self.demanda_equipe),
            ("POST", rf"/demanda/({_UUID})/vistoria", self.demanda_vistoria),
            ("POST", r"/acesso/pedir", self.acesso_pedir), ("GET", r"/acessos", self.acessos),
            ("POST", rf"/acessos/({_UUID})/decidir", self.acesso_decidir),
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
            ("POST", r"/campo/coleta/ambiente", self.coleta_ambiente), ("POST", ROTA_FOTO, self.coleta_foto),
            ("POST", r"/campo/coleta/foto/remover", self.coleta_foto_remover),
        ]
        self._livres = {self.entrar_pagina, self.entrar, self.tema, self.acesso_pedir}

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
            ("X-Content-Type-Options", "nosniff"), ("X-Frame-Options", "DENY"), ("Referrer-Policy", "same-origin"),
            ("Server", "GAEMA-SD"),   # sem versão do Python: o wsgiref só escreve o dele se a aplicação não definir
            ("Cache-Control", "no-store"), ("Cross-Origin-Opener-Policy", "same-origin"),
        ]

    def _despachar(self, environ) -> Resposta:
        host = (environ.get("HTTP_HOST") or "").lower()
        if host not in self.hosts:
            return self._erro(400, "Endereço não permitido. " + L.onde_atende(bool(self.hosts_https)))
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
                corpo = self._ler_corpo(environ, caminho)
                if isinstance(corpo, Resposta):
                    return corpo
                self._arquivos = {}
                if _eh_multipart(environ):
                    try:
                        form, self._arquivos = ler_multipart(corpo, environ.get("CONTENT_TYPE") or "")
                    except ValueError:
                        return self._erro(400, "Pedido malformado: o envio do arquivo não pôde ser lido.",
                                          "Escolha o arquivo de novo e toque em enviar.")
                else:
                    pares = urllib.parse.parse_qs(corpo.decode("utf-8", errors="replace"), keep_blank_values=True)
                    if any(len(v) > 1 for v in pares.values()):
                        return self._erro(400, "Pedido malformado: um campo veio repetido.", "Recarregue a página e envie de novo.")
                    form = {k: v[0] for k, v in pares.items()}
                if funcao not in self._livres and not (sessao and sessao.usuario):
                    return self._ir("/entrar")
                if not sessao or not hmac.compare_digest(form.get("csrf", "").encode("utf-8"), sessao.csrf.encode("utf-8")):
                    return self._erro(403, "Pedido recusado: o token de segurança da página expirou ou não confere.",
                                      "Volte, recarregue a página e tente de novo.")
            else:
                form = {k: v[0] for k, v in urllib.parse.parse_qs(environ.get("QUERY_STRING", ""),
                                                                  keep_blank_values=True).items()}
            ator = self._usuarios_atuais().get(sessao.usuario) if sessao and sessao.usuario else None
            if funcao not in self._livres and ator is None:
                return self._ir("/entrar")
            self._caminho = caminho
            # Cookie Secure: pedido pelo endereço https do Codespaces. O encaminhamento entrega Host = localhost; aí vale o
            # X-Forwarded-Proto, usado SÓ para acrescentar Secure (nunca para aceitar endereço ou origem).
            self._https = bool(self.hosts_https) and (
                host in self.hosts_https or (environ.get("HTTP_X_FORWARDED_PROTO") or "").lower() == "https")
            resp = funcao(sessao, ator, form, *achou.groups())
            log.info("%s %s -> %s", metodo, re.sub(_UUID, "{id}", caminho), resp.status)
            return resp
        return self._erro(405 if achou_caminho else 404,
                          "Esta operação não existe nesta página." if achou_caminho else "Página não encontrada.")

    # ------------------------------------------------------------ sessão, origem, corpo

    def _sessao(self, environ) -> Sessao | None:
        try:
            c = SimpleCookie(environ.get("HTTP_COOKIE", ""))
        except Exception:  # noqa: BLE001 - cookie malformado = sem sessão
            return None
        s = self.sessoes.get(c["sid"].value) if "sid" in c else None
        if s is not None:
            if time.monotonic() - s.usada_em > SESSAO_TTL:
                self.sessoes.pop(s.sid, None)
                return None
            s.usada_em = time.monotonic()
        return s

    def _nova_sessao(self, tema: str = "auto", *, anonima: bool = False) -> Sessao:
        """Sessões anônimas (página de entrada) têm teto próprio e saem primeiro: abrir muitas páginas de entrada não
        derruba quem já entrou. Sessões expiram após SESSAO_TTL segundos sem uso."""
        self._expirar_sessoes()
        anonimas = [k for k, v in self.sessoes.items() if v.usuario is None]
        if anonima and len(anonimas) >= MAX_ANONIMAS:
            self.sessoes.pop(anonimas[0])
        while len(self.sessoes) >= MAX_SESSOES:
            fora = next((k for k, v in self.sessoes.items() if v.usuario is None), next(iter(self.sessoes)))
            self.sessoes.pop(fora)
        s = Sessao(sid=secrets.token_hex(24), tema=tema)
        self.sessoes[s.sid] = s
        return s

    def _expirar_sessoes(self) -> None:
        agora = time.monotonic()
        for k in [k for k, v in self.sessoes.items() if agora - v.usada_em > SESSAO_TTL]:
            self.sessoes.pop(k)

    def _cookie(self, sid: str, *, apagar: bool = False) -> str:
        """Cookie de sessão. `Secure` só quando o pedido veio por https (Codespaces): no acesso local por http o
        navegador descartaria um cookie Secure e o login não funcionaria."""
        return (f"sid={'' if apagar else sid}; HttpOnly; SameSite=Strict; Path=/" + ("; Max-Age=0" if apagar else "")
                + ("; Secure" if getattr(self, "_https", False) else ""))

    def _conferir_origem(self, environ, host: str) -> Resposta | None:
        # Atenção: com Referrer-Policy "no-referrer" o navegador manda "Origin: null" em todo formulário e esta
        # conferência recusaria a própria interface; por isso a política é "same-origin" (nada vaza para fora).
        origem = environ.get("HTTP_ORIGIN")
        if origem is None or self._origem_valida(origem.lower(), host):
            return None
        como = L.como_usar_botoes(bool(self.hosts_https))
        if self.hosts_https:   # só no Codespace (dados sintéticos): mostra o que chegou, para a equipe técnica diagnosticar
            como += f" Detalhe para a equipe técnica: endereço recebido «{host[:120]}»; origem recebida «{origem[:120]}»."
        return self._erro(403, "Pedido recusado: veio de outra página que não esta interface.", como)

    def _origem_valida(self, origem: str, host: str) -> bool:
        if origem in self._origens_aceitas(host):
            return True
        if not self.hosts_https:
            return False
        # Codespace (DEC-032): o encaminhamento do GitHub pode entregar a origem como "null" ou com http/https; a proteção
        # real continua sendo o token CSRF e o cookie SameSite=Strict, que um site de fora não tem. Outro site, outro
        # Codespace ou endereço parecido continuam recusados.
        if origem == "null":
            return True
        partes = urllib.parse.urlsplit(origem)
        return partes.scheme in ("http", "https") and partes.netloc in self.hosts and not (partes.path or partes.query)

    def _origens_aceitas(self, host: str) -> set[str]:
        """Origem do formulário que vale para este pedido. Dentro de um Codespace, o encaminhamento entrega o pedido com
        Host = localhost:PORTA, mas o navegador manda Origin = https://<codespace>-PORTA.<domínio>: esse endereço é
        aceito, calculado SÓ das variáveis do GitHub (hosts_codespaces), nunca de cabeçalho do cliente (DEC-031)."""
        aceitas = {f"https://{host}"} if host in self.hosts_https else {f"http://{host}"}
        return aceitas | {f"https://{h}" for h in self.hosts_https}

    def _ler_corpo(self, environ, caminho: str) -> bytes | Resposta:
        try:
            n = int(environ.get("CONTENT_LENGTH") or 0)
        except ValueError:
            return self._erro(400, "Pedido malformado.")
        if n < 0:
            return self._erro(400, "Pedido malformado.")
        multipart = _eh_multipart(environ)
        if multipart and caminho != ROTA_FOTO:
            return self._erro(400, "Tipo de conteúdo não aceito.")
        if n > (limite_foto() if multipart else LIMITE_CORPO):
            if multipart:
                return self._erro(413, "Foto grande demais.",
                                  f"Envie uma foto de até {int(parametro('interface_foto_maximo_bytes')) // (1024 * 1024)} MB.")
            return self._erro(413, "Pedido grande demais.", "Envie menos texto de uma vez.")
        tipo = (environ.get("CONTENT_TYPE") or "").split(";")[0].strip().lower()
        if n and not multipart and tipo != "application/x-www-form-urlencoded":
            return self._erro(400, "Tipo de conteúdo não aceito.")
        return environ["wsgi.input"].read(n)

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
            menu=self._menu(ator), pagina_atual=getattr(self, "_caminho", ""), barra_campo=self._barra_campo(ator),
            no_codespace=bool(self.hosts_https), **ctx)
        return Resposta(status, html.encode("utf-8"))

    def _erro(self, status: int, mensagem: str, como_resolver: str = "") -> Resposta:
        m = L.explicar(mensagem)
        if como_resolver or m.o_que_houve.startswith("Não foi possível"):
            m = L.Mensagem(mensagem, como_resolver or "Volte e tente de novo. Se continuar, chame a equipe técnica.", "")
        html = self.env.get_template("erro.html.j2").render(
            sessao=None, ator=None, avisos=[], permissoes={}, tema="auto", menu=[], pagina_atual="", barra_campo=None, m=m,
            no_codespace=bool(self.hosts_https))
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
        anonima = sessao if sessao is not None else self._nova_sessao(anonima=True)
        usuarios = []
        for k, a in self._usuarios_atuais().items():
            sim, _ = L.pode_nao_pode(a)
            usuarios.append((k, L.papeis(a.papeis), a.id, ", ".join(sim[:4]) + ("…" if len(sim) > 4 else "") or "consultar"))
        papeis_pediveis = [(p.value, L.PAPEL[p]) for p in Papel if p not in PAPEIS_NAO_PEDIVEIS]
        r = self._pagina("entrar", anonima, None, usuarios=usuarios, papeis_pediveis=papeis_pediveis)
        if sessao is None:
            r.cookie = self._cookie(anonima.sid)
        return r

    def entrar(self, sessao, ator, form):
        escolhido = form.get("usuario", "")
        if sessao is None or escolhido not in self._usuarios_atuais():
            return self._erro(400, "Escolha um usuário de teste da lista.", "Volte à página de entrada e marque um dos usuários.")
        self.sessoes.pop(sessao.sid, None)                      # troca de sessão no login
        nova = self._nova_sessao(sessao.tema)
        nova.usuario = escolhido
        return self._ir("/painel", cookie=self._cookie(nova.sid))

    def _usuarios_atuais(self) -> dict[str, Ator]:
        """Usuários de teste fixos mais os aprovados pelo administrador (PedidoAcesso). Sem autenticação real (R-31)."""
        todos = dict(self.usuarios)
        reservados = set(todos) | {a.id for a in todos.values()}
        for ident, papel in self.nucleo.acessos_de_teste_aprovados(ATOR_PEDIDO_ACESSO):
            if ident not in reservados:
                todos[ident] = Ator.de(ident, papel)
        return todos

    def acesso_pedir(self, sessao, ator, form):
        try:
            papel = Papel(form.get("papel", ""))
        except ValueError:
            self._aviso_erro(sessao, "escolha o papel na lista.")
            return self._ir("/entrar")
        atuais = self._usuarios_atuais()
        try:
            self.nucleo.pedir_acesso_teste(ATOR_PEDIDO_ACESSO, form.get("identificador", "")[:80], papel,
                                           form.get("motivo", "")[:300],
                                           reservados=frozenset(atuais) | {a.id for a in atuais.values()})
            sessao.avisos.append(("ok", "Pedido registrado. Ele aparece para o administrador decidir; aprovado, o usuário de "
                                        "teste surge nesta lista. Não há autenticação real (R-31)."))
        except (ValidacaoFalhou, AcessoNegado, ErroGaema) as e:
            self._aviso_erro(sessao, str(e))
        return self._ir("/entrar")

    def acessos(self, sessao, ator, form):
        try:
            pedidos = self.nucleo.listar(ator, E.PedidoAcesso)
            if not pode(ator, Acao.DECIDIR_ACESSO_TESTE):
                raise AcessoNegado(f"seu papel ({L.papeis(ator.papeis)}) não decide pedidos de acesso de teste")
        except AcessoNegado as e:
            return self._sem_permissao(e)
        ordem = {SituacaoPedidoAcesso.PENDENTE: 0, SituacaoPedidoAcesso.APROVADO: 1, SituacaoPedidoAcesso.REJEITADO: 2}
        pedidos = sorted(pedidos, key=lambda p: (ordem[p.situacao], p.criado_em))
        return self._pagina("acessos", sessao, ator, pedidos=pedidos,
                            pendentes=sum(p.situacao is SituacaoPedidoAcesso.PENDENTE for p in pedidos))

    def acesso_decidir(self, sessao, ator, form, pedido_id):
        decisao = form.get("decisao", "")
        if decisao not in ("aprovar", "rejeitar"):
            return self._erro(400, "Decisão desconhecida.", "Use os botões Aprovar ou Rejeitar.")
        return self._executar(sessao, "/acessos",
                              lambda: self.nucleo.decidir_acesso_teste(ator, pedido_id, decisao == "aprovar",
                                                                       form.get("motivo", "")) and None,
                              "Pedido aprovado: o usuário de teste já aparece na página de entrada." if decisao == "aprovar"
                              else "Pedido rejeitado.")

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
            demandas = [self.nucleo.resumo_demanda(ator, d.id) | {"titulo": d.titulo, "municipio": d.municipio,
                                                                  "equipe_id": d.equipe_id or "", "criado": d.criado_em.date()}
                        for d in self.nucleo.listar(ator, E.Demanda)]
        except AcessoNegado:
            sem_acesso = True
        equipes = {}
        try:
            equipes = {q.id: q.nome for q in self.nucleo.listar(ator, E.Equipe)}
        except AcessoNegado:
            pass
        todas = len(demandas)
        filtros, erros_filtro = self._filtros_painel(form, equipes)
        demandas = [d for d in demandas if self._passa_filtro(d, filtros)]
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
        if pode(ator, Acao.DECIDIR_ACESSO_TESTE):
            n = sum(p.situacao is SituacaoPedidoAcesso.PENDENTE for p in self.nucleo.listar(ator, E.PedidoAcesso))
            if n:
                atencao.append({"tom": "info", "icone": "pessoa", "titulo": f"{n} pedido(s) de usuário de teste esperando decisão",
                                "texto": "Aprove ou rejeite com motivo. Sem autenticação real (R-31).", "href": "/acessos",
                                "link": "Abrir acessos de teste"})
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
        for d in demandas:
            d["equipe_nome"] = equipes.get(d["equipe_id"], "sem equipe definida")
        return self._pagina("painel", sessao, ator, demandas=demandas, sem_acesso=sem_acesso, por_situacao=por_situacao,
                            atencao=atencao, proxima=proxima, pode=sim, nao_pode=nao, filtros=filtros,
                            erros_filtro=erros_filtro, todas=todas, equipes=sorted(equipes.items(), key=lambda x: x[1]),
                            situacoes=[(e.value, L.situacao(e).nome) for e in Estado],
                            pode_criar=pode(ator, Acao.REGISTRAR_AREA_CANDIDATA), razao_criar=self._razao_criar(ator))

    @staticmethod
    def _filtros_painel(form: dict, equipes: dict) -> tuple[dict, list[str]]:
        """Filtros do painel (GET). Só recortam a lista que o núcleo já devolveu ao usuário; nunca ampliam o acesso."""
        f = {"situacao": form.get("situacao", ""), "equipe": form.get("equipe", ""),
             "municipio": form.get("municipio", "").strip()[:80], "de": form.get("de", ""), "ate": form.get("ate", "")}
        erros = []
        if f["situacao"] and f["situacao"] not in {e.value for e in Estado}:
            erros.append("situação desconhecida"); f["situacao"] = ""
        if f["equipe"] and f["equipe"] != "sem" and f["equipe"] not in equipes:
            erros.append("equipe desconhecida"); f["equipe"] = ""
        for k, nome in (("de", "data inicial"), ("ate", "data final")):
            if f[k]:
                try:
                    f[k + "_data"] = date.fromisoformat(f[k])
                except ValueError:
                    erros.append(f"{nome} inválida (use o calendário)"); f[k] = ""
        f["ativo"] = any(f[k] for k in ("situacao", "equipe", "municipio", "de", "ate"))
        return f, erros

    @staticmethod
    def _passa_filtro(d: dict, f: dict) -> bool:
        if f["situacao"] and d["estado"] != f["situacao"]:
            return False
        if f["equipe"] and (d["equipe_id"] or "sem") != f["equipe"]:
            return False
        if f["municipio"] and f["municipio"].casefold() not in (d["municipio"] or "").casefold():
            return False
        if f.get("de_data") and d["criado"] < f["de_data"]:
            return False
        if f.get("ate_data") and d["criado"] > f["ate_data"]:
            return False
        return True

    @staticmethod
    def _razao_criar(ator: Ator) -> str:
        if pode(ator, Acao.REGISTRAR_AREA_CANDIDATA):
            return ""
        return (f"seu papel ({L.papeis(ator.papeis)}) não registra a área indicada que dá origem à demanda; "
                "quem cria demanda pela tela é o analista de triagem.")

    # ---- criar demanda (FonteDado manual → AreaCandidata → Alerta → AreaInteresse → Demanda, numa transação)
    CAMPOS_NOVA = ("titulo", "objetivo", "origem", "descricao", "data_alerta", "municipio", "lat_min", "lat_max", "lon_min",
                   "lon_max", "criterio", "motivo_priorizacao")

    def _pagina_nova(self, sessao, ator, valores: dict, erros: list[str], status: int = 200):
        return self._pagina("demanda_nova", sessao, ator, status, valores={k: valores.get(k, "") for k in self.CAMPOS_NOVA},
                            erros=erros, origens=[(o.value, L.ORIGEM_ALERTA[o]) for o in OrigemAlerta],
                            criterios=list(L.CRITERIO.items()), pode_criar=pode(ator, Acao.REGISTRAR_AREA_CANDIDATA),
                            razao_criar=self._razao_criar(ator), hoje=date.today().isoformat())

    def demanda_nova(self, sessao, ator, form):
        return self._pagina_nova(sessao, ator, {"data_alerta": date.today().isoformat()}, [])

    def demanda_criar(self, sessao, ator, form):
        if not pode(ator, Acao.REGISTRAR_AREA_CANDIDATA):
            return self._sem_permissao(AcessoNegado(self._razao_criar(ator)))
        v = {k: form.get(k, "").strip()[:300 if k in ("objetivo", "descricao", "motivo_priorizacao") else 120]
             for k in self.CAMPOS_NOVA}
        erros = [f"preencha: {nome}" for k, nome in (("titulo", "título"), ("descricao", "o que foi informado"),
                                                     ("data_alerta", "data da informação")) if not v[k]]
        try:
            origem = OrigemAlerta(v["origem"])
        except ValueError:
            erros.append("escolha a origem da informação na lista")
        criterio = None
        if v["criterio"]:
            try:
                criterio = CriterioPriorizacao(v["criterio"])
            except ValueError:
                erros.append("escolha o critério de prioridade na lista")
        try:
            quando = date.fromisoformat(v["data_alerta"]) if v["data_alerta"] else None
            if quando and quando > date.today():
                erros.append("a data da informação não pode estar no futuro")
        except ValueError:
            erros.append("data da informação inválida (use o calendário)"); quando = None
        coords = {}
        for k, nome, lim in (("lat_min", "latitude sul", 90), ("lat_max", "latitude norte", 90),
                             ("lon_min", "longitude oeste", 180), ("lon_max", "longitude leste", 180)):
            try:
                coords[k] = ler_numero(v[k])
                if abs(coords[k]) > lim:
                    erros.append(f"a {nome} deve estar entre -{lim} e {lim}")
            except (TypeError, ValueError):
                erros.append(f"a {nome} precisa ser um número (use vírgula ou ponto)")
        if len(coords) == 4 and not (coords["lat_min"] < coords["lat_max"] and coords["lon_min"] < coords["lon_max"]):
            erros.append("o sul precisa ser menor que o norte e o oeste menor que o leste")
        if erros:
            return self._pagina_nova(sessao, ator, v, erros, 422)
        la1, la2, lo1, lo2 = coords["lat_min"], coords["lat_max"], coords["lon_min"], coords["lon_max"]
        wkt = f"POLYGON(({lo1} {la1}, {lo2} {la1}, {lo2} {la2}, {lo1} {la2}, {lo1} {la1}))"
        base = dict(sintetico=True)
        fonte = E.FonteDado(nome="Informação registrada na interface de teste", tipo=TipoFonte.REGISTRO_MANUAL,
                            provedor="registro manual (interface local)", data_referencia=quando, **base)
        cand = E.AreaCandidata(geometria_wkt=wkt, fonte_ids=[fonte.id], data_deteccao=quando,
                               metodo_selecao="registro manual na interface (sem triagem por satélite)", **base)
        alerta = E.Alerta(origem=origem, descricao=v["descricao"], data_alerta=quando, area_candidata_id=cand.id, **base)
        area = E.AreaInteresse(geometria_wkt=wkt, descricao="Recorte retangular informado na interface (recorte de análise; "
                               "não é imóvel)", origem=OrigemAreaInteresse.DE_CANDIDATA, area_candidata_id=cand.id, **base)
        dem = E.Demanda(titulo=v["titulo"], objetivo=v["objetivo"], alerta_ids=[alerta.id], area_candidata_id=cand.id,
                        area_interesse_id=area.id, criterio_priorizacao=criterio, motivo_priorizacao=v["motivo_priorizacao"],
                        municipio=v["municipio"], **base)
        try:
            self.nucleo.registrar_em_lote(ator, [fonte, cand, alerta, area, dem])
        except AcessoNegado as e:
            return self._sem_permissao(e)
        except (ValidacaoFalhou, ErroGaema) as e:
            m = L.explicar(sanear_texto(str(e))[:400])
            return self._pagina_nova(sessao, ator, v, [m.o_que_houve + " " + m.como_resolver + " Nada foi gravado."], 422)
        sessao.avisos.append(("ok", f"Demanda criada: {L.situacao(Estado.CANDIDATA).nome}. Foram registrados juntos a fonte "
                                    "(registro manual), a área indicada, o alerta e a área de interesse; tudo fica na trilha."))
        return self._ir(f"/demanda/{dem.id}")

    def demanda_equipe(self, sessao, ator, form, demanda_id):
        return self._executar(sessao, f"/demanda/{demanda_id}",
                              lambda: self.nucleo.definir_equipe(ator, demanda_id, form.get("equipe", "")) and None,
                              "Equipe definida para a demanda.")

    def demanda_vistoria(self, sessao, ator, form, demanda_id):
        def fazer():
            d = self.nucleo.ler(ator, E.Demanda, demanda_id)
            if d.estado is not Estado.ATRIBUIDA:
                raise ErroGaema("a vistoria é agendada com a demanda atribuída a uma equipe")
            try:
                quando = date.fromisoformat(form.get("data_planejada", ""))
            except ValueError:
                raise ErroGaema("data da vistoria inválida (use o calendário)") from None
            if quando < date.today():
                raise ErroGaema("a data da vistoria não pode estar no passado")
            protocolos = {p.id for p in self.nucleo.listar(ator, E.VersaoProtocolo)}
            if form.get("protocolo", "") not in protocolos:
                raise ErroGaema("escolha o protocolo na lista")
            objetivo = form.get("objetivo", "").strip()[:300]
            if len(objetivo) < 10:
                raise ErroGaema("descreva o objetivo da vistoria (pelo menos 10 letras)")
            pacote = ("pacote sintético declarado na interface de teste (aparelho simulado)"
                      if form.get("missao_baixada") == "sim" else "")
            self.nucleo.registrar(ator, E.CampanhaVistoria(demanda_id=d.id, equipe_id=d.equipe_id or "",
                                                            versao_protocolo_id=form["protocolo"], objetivo=objetivo,
                                                            data_planejada=quando, pacote_offline=pacote, sintetico=True))
            return quando.strftime("%d/%m/%Y")
        return self._executar(sessao, f"/demanda/{demanda_id}", fazer,
                              "Vistoria agendada para {extra}. Agora a demanda pode passar para “planejada”.")

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
            equipes = {q.id: q.nome for q in self.nucleo.listar(ator, E.Equipe)}
            protocolos = sorted(self.nucleo.listar(ator, E.VersaoProtocolo),
                                key=lambda p: (p.modo is not ModoProtocolo.DESCRITIVO, p.codigo, p.versao_semantica))
            vistorias = sorted((c for c in self.nucleo.listar(ator, E.CampanhaVistoria) if c.demanda_id == demanda_id),
                               key=lambda c: c.data_planejada)
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
        if not pode(ator, Acao.GERIR_EQUIPE):
            razao_equipe = f"seu papel ({L.papeis(ator.papeis)}) não escolhe equipe; quem escolhe é o coordenador."
        elif d.estado not in Nucleo.ESTADOS_SEM_EQUIPE_FIXA:
            razao_equipe = "a equipe só é escolhida antes da atribuição."
        elif not equipes:
            razao_equipe = "não há equipe cadastrada neste banco."
        else:
            razao_equipe = ""
        if not pode(ator, Acao.PLANEJAR_CAMPANHA):
            razao_vistoria = f"seu papel ({L.papeis(ator.papeis)}) não agenda vistoria; quem agenda é o coordenador ou o técnico."
        elif d.estado is not Estado.ATRIBUIDA:
            razao_vistoria = "a vistoria é agendada quando a demanda está “atribuída” a uma equipe."
        elif not protocolos:
            razao_vistoria = "não há protocolo publicado neste banco."
        else:
            razao_vistoria = ""
        return self._pagina("demanda", sessao, ator, d=d, resumo=resumo, transicoes=transicoes, historico=historico,
                            equipes=sorted(equipes.items(), key=lambda x: x[1]), equipe_nome=equipes.get(d.equipe_id or "", ""),
                            razao_equipe=razao_equipe, razao_vistoria=razao_vistoria, protocolos=protocolos,
                            vistorias=vistorias, hoje=date.today().isoformat(),
                            relatorios=relatorios, pode_emitir=pode_emitir, razao_emitir=razao,
                            historico_completo=pode(ator, Acao.VERIFICAR_AUDITORIA),
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
                              "sozinho). O aparelho só fica sabendo quando consultar a central (nesta interface, o "
                              "aparelho simulado consulta ao tocar em “Sincronizar agora”).")

    def auditoria(self, sessao, ator, form):
        try:
            eventos = list(reversed(self.nucleo.eventos_recentes(ator, 30)))
        except AcessoNegado as e:
            return self._sem_permissao(e)
        return self._pagina("auditoria", sessao, ator, eventos=eventos, total=len(self.nucleo.trilha.eventos))

    def verificar_auditoria(self, sessao, ator, form):
        if not pode(ator, Acao.VERIFICAR_AUDITORIA):     # nada é lido antes da permissão
            return self._executar(sessao, "/auditoria", lambda: self.nucleo.verificar_auditoria(ator), "")
        ancora = None
        texto = form.get("ancora_texto", "").strip()
        if texto:
            try:
                ancora = interpretar_ancora(texto)
            except ErroGaema as e:
                self._aviso_erro(sessao, str(e))
                return self._ir("/auditoria")
        if ancora:
            sucesso = "Trilha conferida com a âncora colada: {extra} registros, sem reescrita nem corte até o ponto ancorado."
        else:
            sucesso = ("Cadeia da trilha conferida: {extra} registros. Sem âncora, isso não exclui reescrita completa "
                       "por quem controla o banco; cole a âncora guardada fora para conferir também isso.")
        return self._executar(sessao, "/auditoria", lambda: self.nucleo.verificar_auditoria(ator, ancora), sucesso)

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
            proxima = f"Continue a coleta do ponto {r.get('codigo') or 'em andamento'} (etapa {r['etapa']} de {TOTAL_ETAPAS})."
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
        r["ambiente"] = {**AMBIENTE_VAZIO, **r.get("ambiente", {})}       # o modelo usa StrictUndefined
        r.setdefault("fotos", [])
        return self._pagina("coleta", sessao, ator, etapa=r["etapa"], r=r, missoes=missoes, missao_rotulo=rotulo,
                            total_etapas=TOTAL_ETAPAS, categorias_foto=[(c.value, L.CATEGORIA_FOTO[c]) for c in CategoriaEvidencia],
                            max_fotos=int(parametro("interface_fotos_por_ponto")),
                            max_foto_mb=int(parametro("interface_foto_maximo_bytes")) // (1024 * 1024),
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
        if r.get("max_etapa", 1) < 4:
            self._aviso_erro(sessao, "complete as etapas anteriores antes da conferência.")
            return self._ir("/campo/coleta")
        return self._ir_etapa(r, 5)

    # ---- etapa 3: ambiente do ponto e fotos
    def coleta_ambiente(self, sessao, ator, form):
        bloqueio = self._guarda_coleta(sessao, ator)
        if bloqueio:
            return bloqueio
        r = self._rascunho_ou_novo()
        if r.get("max_etapa", 1) < 3:
            self._aviso_erro(sessao, "complete as etapas anteriores antes do ambiente do ponto.")
            return self._ir("/campo/coleta")
        amb = {k: form.get(k, "").strip()[:120] for k in ("altura", "altura_unidade", "solo", "solo_fonte", "geologia",
                                                           "geologia_fonte", "chuva_nota")}
        amb["chuva"] = form.get("chuva") if form.get("chuva") in ("sim", "nao", "nao_observado") else "nao_observado"
        r["ambiente"] = amb
        self.campo.salvar_rascunho(r)                     # nada se perde, mesmo com erro
        erros = []
        if amb["altura"]:
            try:
                if ler_numero(amb["altura"]) < 0:
                    erros.append("a altura do pasto não pode ser negativa")
            except ValueError:
                erros.append("a altura do pasto precisa ser um número (use vírgula ou ponto)")
            if amb["altura_unidade"] not in PARA_CM:
                erros.append("escolha a unidade da altura da lista")
        if erros:
            sessao.avisos.append(("erro", L.Mensagem("A etapa do ambiente precisa de ajuste.",
                                                     "Corrija o que está indicado e toque em “Salvar e seguir”.", "; ".join(erros))))
            return self._ir("/campo/coleta")
        return self._ir_etapa(r, 4)

    def _pasta_fotos(self) -> Path:
        return self.campo.pasta / "fotos-rascunho"

    def coleta_foto(self, sessao, ator, form):
        bloqueio = self._guarda_coleta(sessao, ator)
        if bloqueio:
            return bloqueio
        r = self._rascunho_ou_novo()
        r.setdefault("fotos", [])
        if r.get("max_etapa", 1) < 3:
            self._aviso_erro(sessao, "complete as etapas anteriores antes de anexar fotos.")
            return self._ir("/campo/coleta")
        arq = getattr(self, "_arquivos", {}).get("foto")
        if not arq or not arq[2]:
            self._aviso_erro(sessao, "escolha uma foto antes de enviar.")
            return self._ir("/campo/coleta")
        if len(r["fotos"]) >= int(parametro("interface_fotos_por_ponto")):
            self._aviso_erro(sessao, f"este ponto já tem {len(r['fotos'])} foto(s), o máximo nesta interface de teste.")
            return self._ir("/campo/coleta")
        try:
            categoria = CategoriaEvidencia(form.get("categoria", ""))
        except ValueError:
            self._aviso_erro(sessao, "escolha o tipo da foto na lista.")
            return self._ir("/campo/coleta")
        nome, tipo, conteudo = arq
        nome = nome.replace("\\", "/").rsplit("/", 1)[-1][:120]
        resultado = validar_anexo(conteudo, nome, tipo)
        if resultado.aceito and resultado.tipo_detectado not in TIPOS_FOTO:
            self._aviso_erro(sessao, "aqui só entra foto (JPEG ou PNG); documento em PDF não é foto do ponto.")
            return self._ir("/campo/coleta")
        if not resultado.aceito:
            sessao.avisos.append(("erro", L.Mensagem("A foto não foi aceita.", "Envie uma foto JPEG ou PNG do próprio aparelho.",
                                                     "; ".join(p.mensagem for p in resultado.problemas)[:300])))
            return self._ir("/campo/coleta")
        if any(f["sha256"] == resultado.sha256 for f in r["fotos"]):
            self._aviso_erro(sessao, "esta mesma foto já foi anexada a este ponto.")
            return self._ir("/campo/coleta")
        pasta = self._pasta_fotos()
        pasta.mkdir(parents=True, exist_ok=True)
        arquivo = resultado.sha256 + "." + nome.rsplit(".", 1)[-1].lower()
        tmp = pasta / (arquivo + ".parcial")
        tmp.write_bytes(conteudo)
        os.replace(tmp, pasta / arquivo)
        r["fotos"].append({"arquivo": arquivo, "nome": nome, "tipo": resultado.tipo_detectado, "tamanho": resultado.tamanho_bytes,
                           "sha256": resultado.sha256, "categoria": categoria.value})
        self.campo.salvar_rascunho(r)
        sessao.avisos.append(("ok", f"Foto {len(r['fotos'])} anexada ao rascunho ({L.CATEGORIA_FOTO[categoria]})."))
        return self._ir("/campo/coleta")

    def coleta_foto_remover(self, sessao, ator, form):
        bloqueio = self._guarda_coleta(sessao, ator)
        if bloqueio:
            return bloqueio
        r = self._rascunho_ou_novo()
        sha = form.get("sha256", "")
        resto = [f for f in r.get("fotos", []) if f["sha256"] != sha]
        if len(resto) != len(r.get("fotos", [])):
            for f in r["fotos"]:
                if f["sha256"] == sha:
                    (self._pasta_fotos() / f["arquivo"]).unlink(missing_ok=True)
            r["fotos"] = resto
            self.campo.salvar_rascunho(r)
            sessao.avisos.append(("ok", "Foto retirada do rascunho."))
        return self._ir("/campo/coleta")

    @staticmethod
    def _observacoes_ambiente(amb: dict, ponto_id: str, quando, ator, chave: str, base: dict) -> list:
        """Altura do pasto (número + unidade), tipo de solo e formação geológica (texto, como no mapa consultado) e chuva
        nas últimas 48 h (sim/não). Sem faixa, limiar ou lista inventada; campo em branco não gera registro."""
        obs = []

        def nova(variavel, valor, unidade, nota="", sufixo=""):
            obs.append(E.Observacao(ponto_id=ponto_id, variavel=variavel, valor_bruto=valor, unidade_bruta=unidade,
                                    observado_em=quando, observador_id=ator.id, nota=nota,
                                    chave_idempotencia=f"{chave}:obs:{sufixo or variavel.value}", **base))
        if amb.get("altura"):
            nova(VariavelCampo.ALTURA_PASTO, amb["altura"], amb.get("altura_unidade", "cm"))
        if amb.get("solo"):
            nova(VariavelCampo.TIPO_SOLO, amb["solo"], "texto",
                 f"fonte informada: {amb['solo_fonte']}" if amb.get("solo_fonte") else "")
        if amb.get("geologia"):
            nova(VariavelCampo.FORMACAO_GEOLOGICA, amb["geologia"], "texto",
                 f"fonte informada: {amb['geologia_fonte']}" if amb.get("geologia_fonte") else "")
        if amb.get("chuva") in ("sim", "nao"):
            nova(VariavelCampo.PRECIPITACAO_RECENTE, "sim" if amb["chuva"] == "sim" else "não", "presenca",
                 amb.get("chuva_nota", ""))
        return obs

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
        for f in (self.campo.rascunho() or {}).get("fotos", []):
            (self._pasta_fotos() / f["arquivo"]).unlink(missing_ok=True)
        self.campo.descartar_rascunho()
        sessao.avisos.append(("ok", "Rascunho descartado. Nada foi salvo no aparelho."))
        return self._ir("/campo")

    def coleta_salvar(self, sessao, ator, form):
        bloqueio = self._guarda_coleta(sessao, ator)
        if bloqueio:
            return bloqueio
        r = self.campo.rascunho()
        if not r or r.get("max_etapa", 1) < TOTAL_ETAPAS:
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
            registros += self._observacoes_ambiente(r.get("ambiente", {}), ponto.id, quando, ator, chave, base)
            fotos = []
            for f in r.get("fotos", []):
                conteudo = (self._pasta_fotos() / f["arquivo"]).read_bytes()
                fotos.append((E.Evidencia(campanha_id=r["missao"], ponto_id=ponto.id, categoria=CategoriaEvidencia(f["categoria"]),
                                          nome_arquivo_original=f["nome"], tipo_mime=f["tipo"], tamanho_bytes=f["tamanho"],
                                          sha256=f["sha256"], registrado_por="",
                                          chave_idempotencia=f"{chave}:foto:{f['sha256'][:16]}", **base), conteudo))
            for i, m in enumerate(r["medicoes"], 1):
                registros.append(E.MedicaoPenetracao(ponto_id=ponto.id, repeticao=i, profundidade_bruta=m["profundidade"],
                                                     profundidade_unidade=m["unidade_p"], resistencia_bruta=m["resistencia"],
                                                     resistencia_unidade=m["unidade_r"], contexto_umidade=m["umidade"],
                                                     medido_em=quando, chave_idempotencia=f"{chave}:pen:{i}", **base))
        except (ValueError, KeyError, OSError) as e:
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
            for ev, conteudo in fotos:
                self.campo.dispositivo.coletar(ev, conteudo)
        except ErroGaema as e:
            self._aviso_erro(sessao, str(e))
            return self._ir("/campo/coleta")
        self.campo.descartar_rascunho()
        for f in r.get("fotos", []):
            (self._pasta_fotos() / f["arquivo"]).unlink(missing_ok=True)
        st = self.campo.status()
        n_obs = sum(isinstance(x, E.Observacao) for x in registros)
        n_med = sum(isinstance(x, E.MedicaoPenetracao) for x in registros)
        sessao.avisos.append(("ok", f"Ponto {ponto.codigo} salvo no aparelho: {n_obs} observação(ões), {n_med} medição(ões) "
                                    f"e {len(fotos)} foto(s). "
                                    f"Na fila: {st['pendentes']}. Sincronize quando houver rede."))
        return self._ir("/campo")


def dataclasses_replace_autoria(reg, ator):
    """Para pré-validar como o núcleo validará: a autoria é preenchida com o usuário logado."""
    return dataclasses.replace(reg, criado_por=ator.id)


class _Silencioso(WSGIRequestHandler):
    timeout = TEMPO_SOCKET   # conexão ociosa ou corpo prometido e não enviado: desiste depois deste tempo

    def log_message(self, formato, *args):   # o log de acesso padrão mostraria caminhos; usamos o logger da aplicação
        pass


class _ServidorComThreads(ThreadingMixIn, WSGIServer):
    """Cada conexão em sua thread: uma conexão lenta ou parada não trava as outras."""
    daemon_threads = True


def _eh_multipart(environ) -> bool:
    return (environ.get("CONTENT_TYPE") or "").split(";")[0].strip().lower() == "multipart/form-data"


def ler_multipart(corpo: bytes, content_type: str) -> tuple[dict[str, str], dict[str, tuple[str, str, bytes]]]:
    """Formulário multipart (biblioteca padrão, sem dependência nova). Devolve (campos de texto, arquivos), em que cada
    arquivo é (nome original, tipo declarado, bytes). Campo repetido, parte sem nome ou corpo que não é multipart: erro."""
    from email.parser import BytesParser
    from email.policy import HTTP
    cabecalho = f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode("latin-1", errors="strict")
    msg = BytesParser(policy=HTTP).parsebytes(cabecalho + corpo)
    if not msg.is_multipart():
        raise ValueError("não é multipart")
    campos: dict[str, str] = {}
    arquivos: dict[str, tuple[str, str, bytes]] = {}
    for parte in msg.iter_parts():
        nome = parte.get_param("name", header="content-disposition")
        if not nome or nome in campos or nome in arquivos:
            raise ValueError("parte sem nome ou repetida")
        dados = parte.get_payload(decode=True) or b""
        arquivo = parte.get_filename()
        if arquivo is not None:
            arquivos[nome] = (arquivo, parte.get_content_type(), dados)
        else:
            campos[nome] = dados.decode("utf-8", errors="replace")
    return campos, arquivos


class _Serializado:
    """Lê o corpo (com limite) FORA da trava e só então atende, um pedido por vez: o núcleo e o SQLite nunca são
    usados por duas threads ao mesmo tempo."""

    def __init__(self, app: Aplicacao):
        self.app = app
        self.trava = threading.Lock()

    def __call__(self, environ, start_response):
        try:
            n = int(environ.get("CONTENT_LENGTH") or 0)
        except ValueError:
            n = -1
        limite = limite_foto() if environ.get("PATH_INFO") == ROTA_FOTO and _eh_multipart(environ) else LIMITE_CORPO
        if 0 < n <= limite:
            environ["wsgi.input"] = io.BytesIO(environ["wsgi.input"].read(n))
        elif n != 0:
            environ["wsgi.input"] = io.BytesIO(b"")   # a aplicação recusa pelo CONTENT_LENGTH (400 ou 413)
        with self.trava:
            return self.app(environ, start_response)


_NOME_CODESPACE = re.compile(r"[a-z0-9][a-z0-9-]{0,99}")
_DOMINIO_CODESPACES = re.compile(r"[a-z0-9-]+(\.[a-z0-9-]+)+")


def hosts_codespaces(porta: int, ambiente: dict | None = None) -> set[str]:
    """Endereço público com que o GitHub Codespaces encaminha a porta (`<codespace>-<porta>.<domínio>`), SÓ quando o
    processo roda dentro de um Codespace (variáveis CODESPACES, CODESPACE_NAME e
    GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN, definidas pelo próprio GitHub). Fora dele, nenhum endereço a mais.
    O servidor continua escutando só em 127.0.0.1: o encaminhamento do Codespaces entra por ali (DEC-029)."""
    amb = os.environ if ambiente is None else ambiente
    if amb.get("CODESPACES") != "true":
        return set()
    nome = (amb.get("CODESPACE_NAME") or "").lower()
    dominio = (amb.get("GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN") or "").lower()
    if not _NOME_CODESPACE.fullmatch(nome) or not _DOMINIO_CODESPACES.fullmatch(dominio):
        return set()
    return {f"{nome}-{porta}.{dominio}"}


def servir(nucleo: Nucleo, porta: int = 8765, *, usuarios: dict[str, Ator] | None = None, campo: Campo | None = None,
           ambiente: dict | None = None):
    """Cria o servidor em 127.0.0.1 (nunca em outra interface). O chamador chama `serve_forever()`."""
    app = Aplicacao(nucleo, hosts_permitidos=set(), usuarios=usuarios, campo=campo)
    servidor = make_server("127.0.0.1", porta, _Serializado(app), server_class=_ServidorComThreads,
                           handler_class=_Silencioso)
    real = servidor.server_address[1]   # porta 0 = escolhida pelo sistema (testes)
    app.hosts_https = hosts_codespaces(real, ambiente)
    app.hosts = {f"127.0.0.1:{real}", f"localhost:{real}"} | app.hosts_https
    return servidor
