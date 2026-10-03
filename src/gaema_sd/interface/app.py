"""Aplicação WSGI da interface local de operação.

Segurança (o que existe e o que NÃO existe):
- escuta só em 127.0.0.1; recusa pedido cujo `Host` não seja o da própria máquina (contra DNS rebinding);
- sessão em cookie HttpOnly + SameSite=Strict, trocada no login; token CSRF em todo formulário e conferência de `Origin`;
- páginas sem JavaScript, sem recurso externo, com Content-Security-Policy restritiva e `no-store`;
- erros mostram mensagem curta (sem traceback); texto de usuário é sempre escapado pelo Jinja2;
- NÃO há autenticação real: o login escolhe um usuário SINTÉTICO de teste. Não usar com dados reais nem fora do
  computador local (R-31, H-A06).
"""

from __future__ import annotations

import hmac
import json
import logging
import re
import secrets
import urllib.parse
from dataclasses import dataclass, field
from http.cookies import SimpleCookie
from pathlib import Path
from wsgiref.simple_server import WSGIRequestHandler, make_server

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

from ..acesso.politica import Acao, Ator, pode
from ..auditoria.trilha import sanear_texto
from ..backup.ancora import ler_ancora
from ..dominio import entidades as E
from ..dominio.enums import Estado, FormatoRelatorio, Papel
from ..erros import (AcessoNegado, AuditoriaCorrompida, ConflitoAtualizacao, ConflitoIdempotencia, ErroGaema,
                     RegistroNaoEncontrado, TransicaoInvalida, ValidacaoFalhou)
from ..estados.documento import DESCRICAO_ESTADO
from ..exportacao import painel as exportacao_painel
from ..nucleo import ESTADOS_COM_RELATORIO, Nucleo

log = logging.getLogger("gaema_sd.interface")

LIMITE_CORPO = 64 * 1024
MAX_SESSOES = 50
_UUID = r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
ROTULO_PAPEL = {
    Papel.ANALISTA_TRIAGEM: "Analista de triagem", Papel.COORDENADOR: "Coordenador", Papel.TECNICO_CAMPO: "Técnico de campo",
    Papel.REVISOR_TECNICO: "Revisor técnico", Papel.MEMBRO_MP: "Membro do Ministério Público", Papel.AUDITOR: "Auditor",
    Papel.ADMINISTRADOR: "Administrador", Papel.SISTEMA: "Sistema",
}
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


@dataclass
class Sessao:
    sid: str
    csrf: str = field(default_factory=lambda: secrets.token_hex(16))
    usuario: str | None = None
    avisos: list[tuple[str, str]] = field(default_factory=list)   # (nivel, texto) mostrados uma vez


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
    def __init__(self, nucleo: Nucleo, *, hosts_permitidos: set[str],
                 usuarios: dict[str, Ator] | None = None):
        if nucleo.modo != "central":
            raise ErroGaema("a interface opera a instalação central (Nucleo em modo 'central')")
        self.nucleo = nucleo
        self.hosts = {h.lower() for h in hosts_permitidos}
        self.usuarios = usuarios or USUARIOS_DE_TESTE
        self.sessoes: dict[str, Sessao] = {}
        self.env = Environment(loader=FileSystemLoader(str(Path(__file__).parent / "modelos")),
                               autoescape=select_autoescape(["j2"], default=True), undefined=StrictUndefined)
        self.env.globals.update(rotulo_papel=lambda ator: ", ".join(ROTULO_PAPEL[p] for p in sorted(ator.papeis, key=lambda x: x.value)),
                                descricao_estado=lambda e: DESCRICAO_ESTADO.get(Estado(e), ""))
        self.rotas = [
            ("GET", r"/", self.inicio), ("GET", r"/entrar", self.entrar_pagina), ("POST", r"/entrar", self.entrar),
            ("POST", r"/sair", self.sair), ("GET", r"/painel", self.painel), ("GET", r"/ajuda", self.ajuda),
            ("GET", rf"/demanda/({_UUID})", self.demanda), ("POST", rf"/demanda/({_UUID})/transitar", self.transitar),
            ("POST", rf"/demanda/({_UUID})/relatorio", self.emitir_relatorio), ("GET", rf"/relatorio/({_UUID})", self.relatorio),
            ("GET", r"/conflitos", self.conflitos), ("GET", rf"/conflitos/({_UUID})", self.conflito),
            ("POST", rf"/conflitos/({_UUID})/resolver", self.resolver),
            ("GET", r"/auditoria", self.auditoria), ("POST", r"/auditoria/verificar", self.verificar_auditoria),
            ("POST", r"/auditoria/ancora", self.gerar_ancora),
            ("GET", r"/exportar", self.exportar_pagina), ("POST", r"/exportar", self.exportar),
            ("GET", r"/backup", self.backup), ("POST", r"/backup/criar", self.backup_criar),
            ("POST", r"/backup/verificar", self.backup_verificar),
        ]

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
                if funcao != self.entrar and not (sessao and sessao.usuario):
                    return self._ir("/entrar")
                if not sessao or not hmac.compare_digest(form.get("csrf", ""), sessao.csrf):
                    return self._erro(403, "Pedido recusado: token de segurança inválido ou ausente. Volte e tente de novo.")
            ator = self.usuarios.get(sessao.usuario) if sessao and sessao.usuario else None
            livre = funcao in (self.entrar_pagina, self.entrar)
            if not livre and ator is None:
                return self._ir("/entrar")
            resp = funcao(sessao, ator, form, *achou.groups())
            log.info("%s %s -> %s", metodo, re.sub(_UUID, "{id}", caminho), resp.status)
            return resp
        return self._erro(405 if achou_caminho else 404,
                          "Operação não permitida nesta página." if achou_caminho else "Página não encontrada.")

    # ------------------------------------------------------------ sessão, origem, corpo

    def _sessao(self, environ) -> Sessao | None:
        c = SimpleCookie(environ.get("HTTP_COOKIE", ""))
        return self.sessoes.get(c["sid"].value) if "sid" in c else None

    def _nova_sessao(self) -> Sessao:
        while len(self.sessoes) >= MAX_SESSOES:
            self.sessoes.pop(next(iter(self.sessoes)))
        s = Sessao(sid=secrets.token_hex(24))
        self.sessoes[s.sid] = s
        return s

    @staticmethod
    def _cookie(sid: str, *, apagar: bool = False) -> str:
        return f"sid={'' if apagar else sid}; HttpOnly; SameSite=Strict; Path=/" + ("; Max-Age=0" if apagar else "")

    @staticmethod
    def _conferir_origem(environ, host: str) -> Resposta | None:
        origem = environ.get("HTTP_ORIGIN")
        if origem is not None and origem.lower() not in (f"http://{host}",):
            return Aplicacao._erro(403, "Pedido recusado: origem diferente da desta interface.")
        return None

    @staticmethod
    def _ler_corpo(environ) -> str | Resposta:
        try:
            n = int(environ.get("CONTENT_LENGTH") or 0)
        except ValueError:
            return Aplicacao._erro(400, "Pedido malformado.")
        if n > LIMITE_CORPO:
            return Aplicacao._erro(413, "Pedido grande demais.")
        tipo = (environ.get("CONTENT_TYPE") or "").split(";")[0].strip().lower()
        if n and tipo != "application/x-www-form-urlencoded":
            return Aplicacao._erro(400, "Tipo de conteúdo não aceito.")
        return environ["wsgi.input"].read(n).decode("utf-8", errors="replace")

    # ------------------------------------------------------------ respostas

    def _pagina(self, nome: str, sessao: Sessao | None, ator: Ator | None, status: int = 200, **ctx) -> Resposta:
        avisos = sessao.avisos[:] if sessao else []
        if sessao:
            sessao.avisos.clear()
        permissoes = {a.name: bool(ator and pode(ator, a)) for a in Acao}
        html = self.env.get_template(nome + ".html.j2").render(
            sessao=sessao, ator=ator, usuario_chave=(sessao.usuario if sessao else None), avisos=avisos,
            permissoes=permissoes, **ctx)
        return Resposta(status, html.encode("utf-8"))

    @staticmethod
    def _erro(status: int, mensagem: str) -> Resposta:
        env = Environment(autoescape=True)
        corpo = env.from_string(
            '<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><title>Erro {{ s }} — GAEMA SD</title></head>'
            '<body><main><h1>Não foi possível concluir</h1><p role="alert">{{ m }}</p>'
            '<p><a href="/painel">Voltar ao painel</a></p></main></body></html>').render(s=status, m=mensagem)
        return Resposta(status, corpo.encode("utf-8"))

    @staticmethod
    def _ir(destino: str, cookie: str | None = None) -> Resposta:
        return Resposta(303, b"", cabecalhos=[("Location", destino)], cookie=cookie)

    def _executar(self, sessao: Sessao, voltar_para: str, fazer, sucesso: str) -> Resposta:
        """Roda uma ação do núcleo; sucesso ou falha viram aviso e redirecionamento (nada reenvia ao atualizar)."""
        try:
            extra = fazer()
            sessao.avisos.append(("ok", sucesso.format(extra=extra) if extra is not None else sucesso))
        except AcessoNegado as e:
            sessao.avisos.append(("erro", "Sem permissão: " + sanear_texto(str(e))[:300]))
        except (TransicaoInvalida, ValidacaoFalhou, ConflitoAtualizacao, ConflitoIdempotencia, AuditoriaCorrompida,
                RegistroNaoEncontrado, ErroGaema) as e:
            sessao.avisos.append(("erro", sanear_texto(str(e))[:400]))
        return self._ir(voltar_para)

    # ------------------------------------------------------------ páginas

    def inicio(self, sessao, ator, form):
        return self._ir("/painel" if ator else "/entrar")

    def entrar_pagina(self, sessao, ator, form):
        anonima = sessao if sessao is not None else self._nova_sessao()
        r = self._pagina("entrar", anonima, None, usuarios=[(k, ROTULO_PAPEL[next(iter(a.papeis))], a.id)
                                                             for k, a in self.usuarios.items()])
        if sessao is None:
            r.cookie = self._cookie(anonima.sid)
        return r

    def entrar(self, sessao, ator, form):
        escolhido = form.get("usuario", "")
        if sessao is None or escolhido not in self.usuarios:
            return self._erro(400, "Escolha um usuário de teste da lista.")
        self.sessoes.pop(sessao.sid, None)                      # troca de sessão no login
        nova = self._nova_sessao()
        nova.usuario = escolhido
        return self._ir("/painel", cookie=self._cookie(nova.sid))

    def sair(self, sessao, ator, form):
        self.sessoes.pop(sessao.sid, None)
        return self._ir("/entrar", cookie=self._cookie("", apagar=True))

    def ajuda(self, sessao, ator, form):
        return self._pagina("ajuda", sessao, ator)

    def painel(self, sessao, ator, form):
        demandas, motivo = [], ""
        try:
            demandas = [self.nucleo.resumo_demanda(ator, d.id) | {"titulo": d.titulo}
                        for d in self.nucleo.listar(ator, E.Demanda)]
        except AcessoNegado as e:
            motivo = sanear_texto(str(e))
        conflitos = len(self.nucleo.listar_conflitos(ator)) if permitido(ator, Acao.RESOLVER_CONFLITO_SINCRONIZACAO) else None
        return self._pagina("painel", sessao, ator, demandas=demandas, sem_acesso=motivo, conflitos=conflitos)

    def demanda(self, sessao, ator, form, demanda_id):
        try:
            d = self.nucleo.ler(ator, E.Demanda, demanda_id)
            resumo = self.nucleo.resumo_demanda(ator, demanda_id)
            transicoes = self.nucleo.transicoes_possiveis(ator, demanda_id)
            historico = self.nucleo.historico_de(ator, "Demanda", demanda_id, 20)
            relatorios = sorted((r for r in self.nucleo.listar(ator, E.Relatorio) if r.demanda_id == demanda_id),
                                key=lambda r: (r.formato.value, r.numero_versao))
        except AcessoNegado as e:
            return self._erro(403, "Sem permissão: " + sanear_texto(str(e))[:300])
        except RegistroNaoEncontrado:
            return self._erro(404, "Demanda não encontrada.")
        pode_emitir = pode(ator, Acao.EMITIR_RELATORIO) and d.estado in ESTADOS_COM_RELATORIO
        return self._pagina("demanda", sessao, ator, d=d, resumo=resumo, transicoes=transicoes, historico=historico,
                            relatorios=relatorios, pode_emitir=pode_emitir,
                            formatos=[f.value for f in FormatoRelatorio],
                            tem_relatorio=bool(relatorios))

    def transitar(self, sessao, ator, form, demanda_id):
        try:
            destino = Estado(form.get("destino", ""))
        except ValueError:
            return self._erro(400, "Destino desconhecido.")
        return self._executar(sessao, f"/demanda/{demanda_id}",
                              lambda: self.nucleo.transitar(ator, demanda_id, destino, motivo=form.get("motivo", "")) and None,
                              f"Demanda movida para {destino.value}.")

    def emitir_relatorio(self, sessao, ator, form, demanda_id):
        try:
            formato = FormatoRelatorio(form.get("formato", ""))
        except ValueError:
            return self._erro(400, "Formato desconhecido.")

        def fazer():
            rel, _ = self.nucleo.emitir_relatorio(ator, demanda_id, formato, motivo_reemissao=form.get("motivo", ""))
            return rel.numero_versao
        return self._executar(sessao, f"/demanda/{demanda_id}", fazer, "Relatório emitido (versão {extra}).")

    def relatorio(self, sessao, ator, form, relatorio_id):
        try:
            conteudo, rel = self.nucleo.abrir_relatorio(ator, relatorio_id)
        except AcessoNegado as e:
            return self._erro(403, "Sem permissão: " + sanear_texto(str(e))[:300])
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
            return self._erro(403, "Sem permissão: " + sanear_texto(str(e))[:300])
        return self._pagina("conflitos", sessao, ator, conflitos=lista)

    def conflito(self, sessao, ator, form, conflito_id):
        try:
            c = self.nucleo.comparar_conflito(ator, conflito_id)
        except AcessoNegado as e:
            return self._erro(403, "Sem permissão: " + sanear_texto(str(e))[:300])
        except RegistroNaoEncontrado:
            return self._erro(404, "Conflito não encontrado.")
        return self._pagina("conflito", sessao, ator, c=c)

    def resolver(self, sessao, ator, form, conflito_id):
        return self._executar(sessao, f"/conflitos/{conflito_id}",
                              lambda: self.nucleo.resolver_conflito_sincronizacao(
                                  ator, conflito_id, form.get("decisao", ""), form.get("motivo", "")),
                              "Decisão registrada. A demanda não volta sozinha: mova-a na página da demanda. "
                              "O aparelho recebe a decisão na próxima consulta.")

    def auditoria(self, sessao, ator, form):
        try:
            eventos = list(reversed(self.nucleo.eventos_recentes(ator, 30)))
        except AcessoNegado as e:
            return self._erro(403, "Sem permissão: " + sanear_texto(str(e))[:300])
        return self._pagina("auditoria", sessao, ator, eventos=eventos, total=len(self.nucleo.trilha.eventos))

    def verificar_auditoria(self, sessao, ator, form):
        ancora, erro = None, None
        if form.get("ancora_arquivo", "").strip():
            try:
                ancora = ler_ancora(form["ancora_arquivo"].strip())
            except ErroGaema as e:
                erro = str(e)
        if erro:
            sessao.avisos.append(("erro", sanear_texto(erro)))
            return self._ir("/auditoria")
        return self._executar(sessao, "/auditoria", lambda: self.nucleo.verificar_auditoria(ator, ancora),
                              "Trilha de auditoria íntegra: {extra} eventos conferidos" + (" (e conferidos com a âncora)." if ancora else "."))

    def gerar_ancora(self, sessao, ator, form):
        try:
            a = self.nucleo.gerar_ancora(ator)
        except (AcessoNegado, ErroGaema) as e:
            sessao.avisos.append(("erro", sanear_texto(str(e))[:300]))
            return self._ir("/auditoria")
        return Resposta(200, json.dumps(a, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8"), "application/json",
                        [("Content-Disposition", f'attachment; filename="ancora-{a["eventos"]:08d}.json"')])

    def exportar_pagina(self, sessao, ator, form):
        return self._pagina("exportar", sessao, ator)

    def exportar(self, sessao, ator, form):
        try:
            pacote = self.nucleo.exportar_painel(ator)
        except AcessoNegado as e:
            sessao.avisos.append(("erro", "Sem permissão: " + sanear_texto(str(e))[:300]))
            return self._ir("/exportar")
        return Resposta(200, exportacao_painel.serializar(pacote), "application/json",
                        [("Content-Disposition", 'attachment; filename="exportacao-gaema-sd.json"')])

    def backup(self, sessao, ator, form):
        try:
            nomes = self.nucleo.listar_backups(ator)
        except AcessoNegado as e:
            return self._erro(403, "Sem permissão: " + sanear_texto(str(e))[:300])
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


def permitido(ator: Ator | None, acao: Acao) -> bool:
    return bool(ator and pode(ator, acao))


class _Silencioso(WSGIRequestHandler):
    def log_message(self, formato, *args):   # o log de acesso padrão mostraria caminhos; usamos o logger da aplicação
        pass


def servir(nucleo: Nucleo, porta: int = 8765, *, usuarios: dict[str, Ator] | None = None):
    """Cria o servidor em 127.0.0.1 (nunca em outra interface). O chamador chama `serve_forever()`."""
    hosts = {f"127.0.0.1:{porta}", f"localhost:{porta}"}
    servidor = make_server("127.0.0.1", porta, Aplicacao(nucleo, hosts_permitidos=hosts, usuarios=usuarios),
                           handler_class=_Silencioso)
    if porta == 0:   # porta escolhida pelo sistema (testes): ajusta os hosts permitidos
        real = servidor.server_address[1]
        servidor.get_app().hosts = {f"127.0.0.1:{real}", f"localhost:{real}"}
    return servidor
