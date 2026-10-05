"""Textos em linguagem comum para a interface. SÓ apresentação: nada aqui muda regra, acesso ou auditoria.

Os nomes técnicos (estados, papéis, ações) continuam no código e na trilha; a tela mostra o nome comum.
Quem age em cada situação é calculado da tabela real de transições (`estados/maquina.py`), não escrito à mão.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from ..acesso.politica import MATRIZ, Acao, Ator
from ..dominio.enums import Estado, Papel
from ..estados.maquina import TABELA, destinos_possiveis

S = Estado
P = Papel

PAPEL = {
    P.ANALISTA_TRIAGEM: "Analista de triagem", P.COORDENADOR: "Coordenador", P.TECNICO_CAMPO: "Técnico de campo",
    P.REVISOR_TECNICO: "Revisor técnico", P.MEMBRO_MP: "Membro do Ministério Público", P.AUDITOR: "Auditor",
    P.ADMINISTRADOR: "Administrador", P.SISTEMA: "Processo automático do sistema",
}

# tom: "neutro" (início/fim), "andamento", "ok", "atencao", "critico". A cor nunca é a única pista: há ícone e texto.
@dataclass(frozen=True)
class Situacao:
    nome: str
    tom: str
    acao: str        # próxima ação, no imperativo


SITUACAO: dict[Estado, Situacao] = {
    S.CANDIDATA: Situacao("Área indicada por satélite (sem conclusão)", "neutro", "Analise o sinal e, se fizer sentido, registre um alerta."),
    S.ALERTA: Situacao("Alerta aguardando triagem", "neutro", "Faça a triagem do alerta."),
    S.EM_TRIAGEM: Situacao("Em triagem", "andamento", "Decida se abre a averiguação e registre o motivo."),
    S.DEMANDA_ABERTA: Situacao("Averiguação aberta", "andamento", "Designe a equipe técnica."),
    S.ATRIBUIDA: Situacao("Equipe designada", "andamento", "Planeje a vistoria: campanha, data e protocolo."),
    S.PLANEJADA: Situacao("Vistoria planejada", "andamento", "Baixe a missão no aparelho e inicie a vistoria."),
    S.EM_CAMPO: Situacao("Vistoria em campo", "andamento", "Colete os pontos no aparelho e sincronize ao terminar."),
    S.COLETA_PARCIAL: Situacao("Vistoria interrompida", "atencao", "Retome a vistoria quando for possível."),
    S.AGUARDANDO_SINCRONIZACAO: Situacao("Aguardando envio dos dados de campo", "andamento",
                                         "Sincronize o aparelho e confira se não ficou conflito."),
    S.EM_VALIDACAO: Situacao("Dados em conferência", "andamento", "Confira os dados recebidos e calcule o diagnóstico."),
    S.AGUARDANDO_REVISAO: Situacao("Aguardando revisão técnica", "andamento",
                                   "Revise o diagnóstico (quem coletou não pode revisar)."),
    S.DIAGNOSTICO_EMITIDO: Situacao("Diagnóstico revisado", "ok", "Emita o relatório e registre a providência decidida."),
    S.EM_TRATATIVA: Situacao("Em tratativa institucional", "andamento", "Registre as providências e o plano de recuperação."),
    S.EM_MONITORAMENTO: Situacao("Em acompanhamento", "andamento", "Acompanhe os marcos do plano e registre cada verificação."),
    S.ENCERRADA: Situacao("Encerrada", "ok", "Nada a fazer. Reabra só com motivo, se surgir fato novo."),
    S.REABERTA: Situacao("Reaberta", "atencao", "Indique por onde a demanda deve recomeçar."),
    S.DUPLICADA: Situacao("Duplicada de outra demanda", "neutro", "Nada a fazer aqui: acompanhe a demanda original."),
    S.DADOS_INSUFICIENTES: Situacao("Faltam dados", "atencao", "Complete os dados que faltam ou cancele com justificativa."),
    S.SEM_ACESSO: Situacao("Sem acesso à área", "atencao", "Replaneje a vistoria."),
    S.GEOMETRIA_INCONSISTENTE: Situacao("Área com desenho inválido", "critico", "Corrija o desenho da área."),
    S.CONFLITO_SINCRONIZACAO: Situacao("Conflito: aguardando decisão do coordenador", "critico",
                                       "Abra o conflito e decida qual versão vale."),
    S.CANCELADA_JUSTIFICADA: Situacao("Cancelada (com justificativa)", "neutro", "Nada a fazer. Reabra só com motivo, se surgir fato novo."),
    S.DEVOLVIDA_COMPLEMENTACAO: Situacao("Devolvida para completar", "atencao", "Complete a coleta ou a análise indicada."),
}

TOM = {"neutro": "Situação inicial ou final", "andamento": "Em andamento", "ok": "Concluída",
       "atencao": "Precisa de atenção", "critico": "Bloqueada: decisão necessária"}

CRITERIO = {"ART17_I": "Art. 17, I — erosão de grande porte (registro humano)",
            "ART17_II": "Art. 17, II — impacto supramunicipal (registro humano)",
            "ART17_III": "Art. 17, III — degradação severa (registro humano; o sistema não calcula)",
            "ART17_IV": "Art. 17, IV — encaminhamento de Promotoria (registro humano)",
            "OUTRO": "Outro critério (registro humano)"}

ACAO_AUDITORIA = {
    "CRIAR": "Registro criado", "ATUALIZAR": "Registro alterado", "TRANSICAO": "Mudança de situação",
    "TRANSICAO_RECUSADA": "Mudança de situação recusada", "REENVIO_IDEMPOTENTE": "Reenvio sem duplicar",
    "ACESSO_NEGADO": "Acesso negado", "LEITURA_RESTRITA": "Consulta a dado restrito",
    "LISTAGEM_RESTRITA": "Listagem de dados restritos", "EXPORTACAO": "Pacote exportado",
    "CONFLITO_SINCRONIZACAO": "Conflito de sincronização aberto",
    "CONFLITO_SINCRONIZACAO_RESOLVIDO": "Conflito decidido pelo coordenador",
    "BACKUP_CRIADO": "Backup criado", "BACKUP_VERIFICADO": "Backup conferido",
    "VERIFICACAO_EVIDENCIA": "Evidência conferida", "REPRODUCAO_DIAGNOSTICO": "Diagnóstico refeito para conferência",
    "RELATORIO_NAO_CONFERE": "Relatório adulterado (não aberto)", "CONSULTA_DECISAO_CONFLITO": "Aparelho consultou decisões",
}

ACAO_PERMISSAO = {
    Acao.REGISTRAR_FONTE: "registrar fontes de dados", Acao.REGISTRAR_AREA_CANDIDATA: "registrar áreas indicadas",
    Acao.REGISTRAR_ALERTA: "registrar alertas", Acao.REGISTRAR_DEMANDA: "registrar demandas",
    Acao.DEFINIR_AREA_INTERESSE: "definir a área de interesse", Acao.GERIR_EQUIPE: "formar equipes",
    Acao.PLANEJAR_CAMPANHA: "planejar vistorias", Acao.COLETAR_CAMPO: "coletar dados de campo",
    Acao.REGISTRAR_EVIDENCIA: "registrar fotos e documentos", Acao.PUBLICAR_PROTOCOLO: "publicar protocolos",
    Acao.COMPUTAR_DIAGNOSTICO: "calcular o diagnóstico", Acao.REVISAR_DIAGNOSTICO: "revisar o diagnóstico",
    Acao.EMITIR_RELATORIO: "emitir relatórios", Acao.REGISTRAR_PROVIDENCIA: "registrar providências",
    Acao.GERIR_PLANO_MONITORAMENTO: "gerir plano e marcos", Acao.REGISTRAR_INTEGRACAO: "registrar integrações",
    Acao.LER_RESTRITO: "ver dados restritos (demandas, pontos, relatórios)", Acao.EXPORTAR: "exportar o pacote",
    Acao.VERIFICAR_AUDITORIA: "conferir a trilha de auditoria", Acao.SINCRONIZAR: "sincronizar o aparelho",
    Acao.RESOLVER_CONFLITO_SINCRONIZACAO: "decidir conflitos de sincronização", Acao.GERIR_BACKUP: "criar e conferir backups",
}

CAMPO = {"valor_bruto": "Valor anotado", "valor_normalizado": "Valor convertido", "unidade_bruta": "Unidade anotada",
         "nota": "Nota", "variavel": "Variável observada", "latitude": "Latitude", "longitude": "Longitude",
         "precisao_gps_m": "Precisão do GPS (m)", "codigo": "Código do ponto", "categoria": "Categoria",
         "resistencia_bruta": "Resistência anotada", "profundidade_bruta": "Profundidade anotada",
         "observado_em": "Observado em", "capturado_em": "Capturado em", "medido_em": "Medido em"}


def papeis(papeis_) -> str:
    return ", ".join(PAPEL[p] for p in sorted(papeis_, key=lambda x: x.value))


def situacao(estado) -> Situacao:
    return SITUACAO[Estado(estado) if not isinstance(estado, Estado) else estado]


def quem_age(estado) -> str:
    """Papéis que podem tirar a demanda desta situação, segundo a tabela real de transições."""
    e = Estado(estado) if not isinstance(estado, Estado) else estado
    todos = set()
    for d in destinos_possiveis(e):
        if d is S.CANCELADA_JUSTIFICADA:
            continue
        todos |= TABELA[(e, d)].papeis
    return papeis(todos) if todos else "ninguém (situação final)"


def pode_nao_pode(ator: Ator) -> tuple[list[str], list[str]]:
    sim, nao = [], []
    for acao, texto in ACAO_PERMISSAO.items():
        (sim if ator.papeis & MATRIZ[acao] else nao).append(texto)
    return sim, nao


def acao_auditoria(codigo: str) -> str:
    return ACAO_AUDITORIA.get(codigo, codigo.replace("_", " ").capitalize())


def nome_estado(codigo) -> str:
    if not codigo:
        return "—"
    try:
        return situacao(codigo).nome
    except (ValueError, KeyError):
        return str(codigo)


def nome_campo(campo: str) -> str:
    return CAMPO.get(campo, campo.replace("_", " ").capitalize())


def _trocar_codigos(texto: str) -> str:
    """Troca nomes técnicos de estado e de papel, dentro de uma mensagem, pelos nomes comuns."""
    for e in sorted(Estado, key=lambda x: -len(x.value)):
        texto = re.sub(rf"\b{e.value}\b", f"“{SITUACAO[e].nome}”", texto)
    for p in sorted(Papel, key=lambda x: -len(x.value)):
        texto = re.sub(rf"\b{p.value}\b", PAPEL[p], texto)
    return texto


# (padrão, o que houve, como resolver) — o primeiro que casar vale
_REGRAS = [
    (r"motivo obrigatório|exige motivo|mínimo 10 caracteres",
     "O motivo está vazio ou curto demais.", "Escreva pelo menos 10 letras explicando o porquê e tente de novo."),
    (r"só pode ser feita por",
     "Seu papel não pode fazer esta mudança de situação.", "Peça a quem tem o papel indicado no detalhe abaixo."),
    (r"não é possível ir de",
     "Essa mudança não existe a partir da situação atual.", "Use um dos botões disponíveis nesta página."),
    (r"pré-condições não atendidas",
     "Ainda falta algo antes desta mudança.", "Veja no detalhe o que falta, complete e tente de novo."),
    (r"relatório só é emitido",
     "O relatório só pode ser emitido depois do diagnóstico revisado.", "Conclua a revisão técnica antes."),
    (r"mudou na central depois do conflito",
     "O registro mudou na central depois que o conflito foi aberto.",
     "Mantenha a versão da central ou peça ao técnico um novo envio a partir da versão atual."),
    (r"já resolvido", "Este conflito já foi decidido.", "Nada a fazer; volte à lista de conflitos."),
    (r"não confere", "A conferência encontrou diferença: o arquivo ou o backup não bate com o registrado.",
     "Não use este arquivo. Chame a equipe técnica e guarde o que foi encontrado."),
    (r"alterado por outra pessoa", "Outra pessoa alterou este registro enquanto você editava.",
     "Recarregue a página e refaça a alteração."),
    (r"âncora", "Não foi possível usar o arquivo de âncora.", "Confira o caminho do arquivo e se ele não foi alterado."),
    (r"nome de backup inválido", "O nome do backup não é válido.", "Escolha um backup da lista."),
    (r"não permitida para papéis|Sem permissão|AcessoNegado|inativo",
     "Seu papel não pode fazer isso.", "Entre com o papel adequado ou peça a quem tem a permissão."),
    (r"equipe", "O usuário não faz parte da equipe desta vistoria.", "Peça ao coordenador para incluir você na equipe."),
    (r"estado de coleta|não aceita dado novo de campo",
     "A demanda não está mais em fase de coleta.", "Peça ao coordenador para devolvê-la para complementação, se for o caso."),
]


@dataclass(frozen=True)
class Mensagem:
    o_que_houve: str
    como_resolver: str
    detalhe: str


def explicar(texto_tecnico: str) -> Mensagem:
    for padrao, houve, resolver in _REGRAS:
        if re.search(padrao, texto_tecnico, re.IGNORECASE):
            return Mensagem(houve, resolver, _trocar_codigos(texto_tecnico))
    return Mensagem("Não foi possível concluir a operação.",
                    "Confira os dados e tente de novo. Se continuar, chame a equipe técnica.", _trocar_codigos(texto_tecnico))


# ---- onde a interface roda (este computador ou um Codespace do GitHub) ------------------------------------------------

def onde_atende(no_codespace: bool) -> str:
    if no_codespace:
        return "Esta interface só atende pelo endereço do seu Codespace (aba PORTAS, porta 8765)."
    return "Esta interface só atende neste computador."


def como_usar_botoes(no_codespace: bool) -> str:
    if no_codespace:
        return "Use os botões desta interface, aberta pelo endereço do seu Codespace (aba PORTAS, porta 8765)."
    return "Use os botões desta interface, aberta em 127.0.0.1."


def rodape_local(no_codespace: bool) -> str:
    if no_codespace:
        return ("GAEMA SD — protótipo de teste rodando no seu Codespace do GitHub, com porta privada (só você acessa); "
                "dados sintéticos; nada é enviado a sistemas externos.")
    return "GAEMA SD — protótipo local, só neste computador (127.0.0.1); nada é enviado para fora."


# ---- coleta: tipos de foto (CategoriaEvidencia) em linguagem comum ------------------------------------------------------
from ..dominio.enums import CategoriaEvidencia as _C  # noqa: E402

CATEGORIA_FOTO = {_C.FOTO_PANORAMICA: "Foto panorâmica da área", _C.FOTO_SOLO: "Foto do solo",
                  _C.FOTO_FORRAGEIRA: "Foto do capim (forrageira)", _C.FOTO_INVASORA: "Foto de planta invasora",
                  _C.FOTO_CUPINZEIRO: "Foto de cupinzeiro", _C.FOTO_EROSAO: "Foto de erosão",
                  _C.FOTO_MEDICAO: "Foto da medição", _C.DOCUMENTO: "Documento", _C.OUTRA: "Outra"}
CATEGORIA_FOTO_POR_CODIGO = {c.value: t for c, t in CATEGORIA_FOTO.items()}

