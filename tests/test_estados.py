import dataclasses
from collections import deque

import pytest

from gaema_sd.acesso import Ator
from gaema_sd.auditoria import TrilhaAuditoria
from gaema_sd.dominio.enums import ESTADOS_EXCEPCIONAIS, Estado, Papel
from gaema_sd.erros import AcessoNegado, TransicaoInvalida
from gaema_sd.estados import TABELA, ContextoTransicao, destinos_possiveis, reversao, transitar

S = Estado

CTX_OK = ContextoTransicao(
    geometria_valida=True, fonte_registrada=True, area_interesse_definida=True, equipe_definida=True,
    campanha_planejada=True, protocolo_definido=True, missao_baixada=True, nota_acesso_registrada=True,
    pontos_coletados=3, diagnostico_computado=True, revisao_aprovada=True, relatorio_emitido=True,
    providencia_registrada=True, marcos_monitoramento=2,
)

CAMINHO_FELIZ = [
    (S.ALERTA, "sistema", ""),
    (S.EM_TRIAGEM, "analista", ""),
    (S.DEMANDA_ABERTA, "membro", "abertura para averiguação sintética"),
    (S.ATRIBUIDA, "coord", ""),
    (S.PLANEJADA, "coord", ""),
    (S.EM_CAMPO, "tecnico", ""),
    (S.COLETA_PARCIAL, "tecnico", "chuva forte interrompeu a coleta"),
    (S.EM_CAMPO, "tecnico", ""),
    (S.AGUARDANDO_SINCRONIZACAO, "tecnico", ""),
    (S.EM_VALIDACAO, "sistema", ""),
    (S.AGUARDANDO_REVISAO, "coord", ""),
    (S.DIAGNOSTICO_EMITIDO, "revisor", ""),
    (S.EM_TRATATIVA, "membro", "reunião de tratativa designada"),
    (S.EM_MONITORAMENTO, "membro", ""),
    (S.ENCERRADA, "membro", "marcos verificados e cumpridos"),
    (S.REABERTA, "membro", "nova notícia sobre a mesma área"),
]


@pytest.fixture
def demanda(cenario):
    return cenario["Demanda"][0]


def test_23_estados_16_normais_7_excepcionais():
    assert len(Estado) == 23 and len(ESTADOS_EXCEPCIONAIS) == 7


def test_caminho_feliz_completo_auditado(demanda, atores):
    trilha = TrilhaAuditoria()
    d = demanda
    for destino, quem, motivo in CAMINHO_FELIZ:
        d = transitar(d, destino, atores[quem], contexto=CTX_OK, trilha=trilha, motivo=motivo)
        assert d.estado is destino
    assert trilha.verificar() == len(CAMINHO_FELIZ)
    ev = trilha.eventos[2]
    assert (ev.estado_origem, ev.estado_destino, ev.ator_id) == ("EM_TRIAGEM", "DEMANDA_ABERTA",
                                                                atores["membro"].id)
    assert ev.motivo == "abertura para averiguação sintética"


def test_transicao_inexistente_lista_destinos(demanda, atores):
    with pytest.raises(TransicaoInvalida, match="destinos possíveis"):
        transitar(demanda, S.DIAGNOSTICO_EMITIDO, atores["coord"], contexto=CTX_OK, trilha=TrilhaAuditoria())


def test_acesso_indevido_na_transicao(demanda, atores):
    d = dataclasses.replace(demanda, estado=S.AGUARDANDO_REVISAO)
    trilha = TrilhaAuditoria()
    for intruso in ("tecnico", "coord", "membro", "admin", "auditor"):
        with pytest.raises(AcessoNegado):
            transitar(d, S.DIAGNOSTICO_EMITIDO, atores[intruso], contexto=CTX_OK, trilha=trilha)
    assert trilha.eventos == ()  # nada muda; recusa é auditada pelo Nucleo


def test_usuario_inativo_nao_transita(demanda):
    inativo = Ator("x", frozenset({Papel.SISTEMA}), ativo=False)
    with pytest.raises(AcessoNegado, match="inativo"):
        transitar(demanda, S.ALERTA, inativo, contexto=CTX_OK, trilha=TrilhaAuditoria())


def test_motivo_obrigatorio(demanda, atores):
    d = dataclasses.replace(demanda, estado=S.EM_TRIAGEM)
    with pytest.raises(TransicaoInvalida, match="motivo"):
        transitar(d, S.DEMANDA_ABERTA, atores["membro"], contexto=CTX_OK, trilha=TrilhaAuditoria(), motivo="ok")


def test_precondicao_falha_explica(demanda, atores):
    ctx = dataclasses.replace(CTX_OK, pendencias_sincronizacao=2, conflitos_abertos=1)
    d = dataclasses.replace(demanda, estado=S.AGUARDANDO_SINCRONIZACAO)
    with pytest.raises(TransicaoInvalida, match="pendentes de sincronização.*conflito"):
        transitar(d, S.EM_VALIDACAO, atores["sistema"], contexto=ctx, trilha=TrilhaAuditoria())


def test_sinal_remoto_nao_vira_diagnostico_sem_revisao(demanda, atores):
    ctx = dataclasses.replace(CTX_OK, revisao_aprovada=False)
    d = dataclasses.replace(demanda, estado=S.AGUARDANDO_REVISAO)
    with pytest.raises(TransicaoInvalida, match="revisão"):
        transitar(d, S.DIAGNOSTICO_EMITIDO, atores["revisor"], contexto=ctx, trilha=TrilhaAuditoria())


def test_revisor_que_coletou_nao_emite(demanda, atores):
    ctx = dataclasses.replace(CTX_OK, revisor_participou_da_coleta=True)
    d = dataclasses.replace(demanda, estado=S.AGUARDANDO_REVISAO)
    with pytest.raises(TransicaoInvalida, match="participou da coleta"):
        transitar(d, S.DIAGNOSTICO_EMITIDO, atores["revisor"], contexto=ctx, trilha=TrilhaAuditoria())


def test_excecao_so_retorna_ao_estado_anterior(demanda, atores):
    t = TrilhaAuditoria()
    d = dataclasses.replace(demanda, estado=S.EM_TRIAGEM)
    d = transitar(d, S.GEOMETRIA_INCONSISTENTE, atores["analista"], contexto=CTX_OK, trilha=t,
                  motivo="polígono com auto-interseção")
    assert d.estado_anterior is S.EM_TRIAGEM
    with pytest.raises(TransicaoInvalida, match="estado anterior"):
        transitar(d, S.ALERTA, atores["analista"], contexto=CTX_OK, trilha=t, motivo="geometria corrigida ok")
    ruim = dataclasses.replace(CTX_OK, geometria_valida=False)
    with pytest.raises(TransicaoInvalida, match="geometria"):
        transitar(d, S.EM_TRIAGEM, atores["analista"], contexto=ruim, trilha=t, motivo="geometria corrigida ok")
    d = transitar(d, S.EM_TRIAGEM, atores["analista"], contexto=CTX_OK, trilha=t, motivo="geometria corrigida ok")
    assert d.estado is S.EM_TRIAGEM and d.estado_anterior is None


def test_duplicada_exige_original(demanda, atores):
    with pytest.raises(TransicaoInvalida, match="original"):
        transitar(demanda, S.DUPLICADA, atores["analista"], contexto=CTX_OK, trilha=TrilhaAuditoria(),
                  motivo="mesma área de outra demanda")
    d = dataclasses.replace(demanda, duplicada_de="outra-demanda-sintetica")
    d = transitar(d, S.DUPLICADA, atores["analista"], contexto=CTX_OK, trilha=TrilhaAuditoria(),
                  motivo="mesma área de outra demanda")
    assert d.estado is S.DUPLICADA


def test_sem_acesso_e_conflito_de_sincronizacao(demanda, atores):
    t = TrilhaAuditoria()
    d = dataclasses.replace(demanda, estado=S.EM_CAMPO)
    d = transitar(d, S.SEM_ACESSO, atores["tecnico"], contexto=CTX_OK, trilha=t, motivo="porteira trancada")
    d = transitar(d, S.PLANEJADA, atores["coord"], contexto=CTX_OK, trilha=t, motivo="nova data agendada")
    d = dataclasses.replace(d, estado=S.AGUARDANDO_SINCRONIZACAO)
    d = transitar(d, S.CONFLITO_SINCRONIZACAO, atores["sistema"], contexto=CTX_OK, trilha=t,
                  motivo="duas versões do ponto P01")
    aberto = dataclasses.replace(CTX_OK, conflitos_abertos=1)
    with pytest.raises(TransicaoInvalida):
        transitar(d, S.AGUARDANDO_SINCRONIZACAO, atores["coord"], contexto=aberto, trilha=t,
                  motivo="mantida versão do técnico")
    d = transitar(d, S.AGUARDANDO_SINCRONIZACAO, atores["coord"], contexto=CTX_OK, trilha=t,
                  motivo="mantida versão do técnico")
    assert d.estado is S.AGUARDANDO_SINCRONIZACAO


def test_cancelamento_justificado_e_reabertura(demanda, atores):
    for e in Estado:
        pode = (e, S.CANCELADA_JUSTIFICADA) in TABELA
        assert pode == (e not in {S.ENCERRADA, S.CANCELADA_JUSTIFICADA, S.DUPLICADA}), e
    d = transitar(demanda, S.CANCELADA_JUSTIFICADA, atores["coord"], contexto=CTX_OK,
                  trilha=TrilhaAuditoria(), motivo="área fora da atribuição")
    assert destinos_possiveis(d.estado) == [S.REABERTA]


def test_administrador_e_auditor_nunca_movem_o_fluxo():
    for t in TABELA.values():
        assert not ({Papel.ADMINISTRADOR, Papel.AUDITOR} & t.papeis), t


def test_todos_os_estados_alcancaveis_e_com_saida():
    vistos, fila = {S.CANDIDATA}, deque([S.CANDIDATA])
    while fila:
        for d in destinos_possiveis(fila.popleft()):
            if d not in vistos:
                vistos.add(d)
                fila.append(d)
    assert vistos == set(Estado)
    assert all(destinos_possiveis(e) for e in Estado)


def test_reversao_quando_existe():
    assert reversao(TABELA[(S.EM_CAMPO, S.COLETA_PARCIAL)]).destino is S.EM_CAMPO
    assert reversao(TABELA[(S.AGUARDANDO_REVISAO, S.DIAGNOSTICO_EMITIDO)]) is None


def test_demanda_original_nao_e_alterada(demanda, atores):
    transitar(demanda, S.ALERTA, atores["sistema"], contexto=CTX_OK, trilha=TrilhaAuditoria())
    assert demanda.estado is S.CANDIDATA
