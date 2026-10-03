"""Tradução PURA (sem rede) de uma submissão de campo para itens de sincronização.

O formato de entrada é NEUTRO e definido aqui: as chaves são os nomes dos campos do XLSForm
(`xlsform.py`), as repetições são listas de dicionários e o geopoint segue o padrão ODK
("latitude longitude altitude precisão", separados por espaço). O formato REAL de exportação do
Survey123 NÃO foi verificado. Quem grava é o núcleo (`Nucleo.receber_sincronizacao`), não este módulo.
Reimportar a mesma submissão gera os mesmos identificadores e chaves: o núcleo trata como reenvio.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from ..dominio import entidades as E
from ..dominio.enums import StatusSincronizacao, VariavelCampo
from ..erros import ErroGaema
from ..sincronizacao.item import ItemSincronizacao
from .xlsform import VARIAVEIS_PRESENCA, nome_presenca

_NS = uuid.UUID("00000000-0000-4000-8000-0000000f5f5f")
_PRESENCA = {"sim": "sim", "nao": "não"}


def _id(*partes: str) -> str:
    return str(uuid.uuid5(_NS, "|".join(partes)))


def _exigir(sub: dict, *campos: str) -> None:
    faltando = [c for c in campos if sub.get(c) in (None, "")]
    if faltando:
        raise ErroGaema(f"submissão sem campo obrigatório: {', '.join(faltando)}")


def _geopoint(texto: str) -> tuple[float, float, float | None, float | None]:
    try:
        p = [float(x) for x in str(texto).split()]
    except ValueError as e:
        raise ErroGaema("localização ilegível (esperado 'lat lon altitude precisão')") from e
    if len(p) < 2:
        raise ErroGaema("localização incompleta (esperado ao menos latitude e longitude)")
    return p[0], p[1], (p[2] if len(p) > 2 else None), (p[3] if len(p) > 3 else None)


def nao_traduzidos(sub: dict[str, Any]) -> list[str]:
    """Campos preenchidos que esta tradução NÃO leva ao núcleo: condição e nota de acesso são da campanha
    (`campos_de_campanha`) e as fotos entram por `Nucleo.registrar_evidencia`, com o arquivo e o hash."""
    achados = []
    if sub.get("condicao_acesso"):
        achados.append("condicao_acesso")
    if sub.get("nota_acesso"):
        achados.append("nota_acesso")
    if sub.get("fotos"):
        achados.append("fotos")
    return achados


def campos_de_campanha(sub: dict[str, Any]) -> dict[str, str]:
    """Condição e nota de acesso declaradas em campo, para quem for atualizar a CampanhaVistoria (decisão humana)."""
    return {"condicao_acesso": sub.get("condicao_acesso") or "", "nota_acesso": sub.get("nota_acesso") or ""}


def traduzir_submissao(sub: dict[str, Any], *, ignorar_nao_traduzidos: bool = False) -> list[ItemSincronizacao]:
    """Devolve, em ordem de envio: ponto, observações, medições.

    Campo coletado que não tem destino aqui (condição/nota de acesso e fotos) NÃO é descartado em silêncio: levanta
    ErroGaema, a menos que quem chama declare que cuidará deles (`ignorar_nao_traduzidos=True`)."""
    pendentes = nao_traduzidos(sub)
    if pendentes and not ignorar_nao_traduzidos:
        raise ErroGaema("a submissão traz campos que esta tradução não leva ao núcleo: " + ", ".join(pendentes)
                        + " (trate-os à parte e repita com ignorar_nao_traduzidos=True)")
    _exigir(sub, "campanha_id", "dispositivo_id", "observador_id", "capturado_em", "codigo_ponto", "localizacao")
    quando = datetime.fromisoformat(sub["capturado_em"])
    lat, lon, alt, precisao = _geopoint(sub["localizacao"])
    base = {"criado_em": quando, "criado_por": sub["observador_id"], "sintetico": bool(sub.get("sintetico", False)),
            "status_sincronizacao": StatusSincronizacao.PENDENTE}
    chave = f"{sub['dispositivo_id']}:{sub['codigo_ponto']}"
    ponto_id = _id(sub["campanha_id"], chave, "ponto")
    registros: list = [E.PontoAmostral(
        id=ponto_id, campanha_id=sub["campanha_id"], codigo=sub["codigo_ponto"], latitude=lat, longitude=lon,
        altitude_m=alt, precisao_gps_m=precisao, capturado_em=quando, dispositivo_id=sub["dispositivo_id"],
        chave_idempotencia=chave, **base)]

    def obs(sufixo: str, variavel: VariavelCampo, valor: str, unidade: str, nota: str = "") -> E.Observacao:
        return E.Observacao(id=_id(sub["campanha_id"], chave, "obs", sufixo), ponto_id=ponto_id, variavel=variavel,
                            valor_bruto=valor, unidade_bruta=unidade, nota=nota, observado_em=quando,
                            observador_id=sub["observador_id"], chave_idempotencia=f"{chave}:obs:{sufixo}", **base)

    for v in VARIAVEIS_PRESENCA:
        bruto = sub.get(nome_presenca(v))
        if bruto in (None, ""):
            continue
        if bruto not in _PRESENCA:
            raise ErroGaema(f"{nome_presenca(v)}: valor '{bruto}' inválido (use sim ou nao)")
        registros.append(obs(v.value, v, _PRESENCA[bruto], "presenca"))
    if sub.get("hipotese_alternativa"):
        registros.append(obs("HIPOTESE_ALTERNATIVA", VariavelCampo.HIPOTESE_ALTERNATIVA,
                             sub["hipotese_alternativa"], "texto"))
    for i, o in enumerate(sub.get("outras_observacoes") or [], 1):
        _exigir(o, "outra_variavel", "outra_valor_bruto", "outra_unidade_bruta")
        try:
            variavel = VariavelCampo(o["outra_variavel"])
        except ValueError as e:
            raise ErroGaema(f"variável desconhecida: {o['outra_variavel']}") from e
        registros.append(obs(f"outra{i}", variavel, str(o["outra_valor_bruto"]), o["outra_unidade_bruta"],
                             o.get("outra_nota") or ""))
    repeticoes = [str(m.get("pen_repeticao")) for m in (sub.get("penetrometria") or [])]
    if len(repeticoes) != len(set(repeticoes)):
        raise ErroGaema("penetrometria com número de repetição duplicada no mesmo ponto")
    for i, m in enumerate(sub.get("penetrometria") or [], 1):
        _exigir(m, "pen_repeticao", "pen_profundidade", "pen_profundidade_unidade", "pen_resistencia",
                "pen_resistencia_unidade")
        registros.append(E.MedicaoPenetracao(
            id=_id(sub["campanha_id"], chave, "pen", str(m["pen_repeticao"])), ponto_id=ponto_id,
            repeticao=int(m["pen_repeticao"]), profundidade_bruta=str(m["pen_profundidade"]),
            profundidade_unidade=m["pen_profundidade_unidade"], resistencia_bruta=str(m["pen_resistencia"]),
            resistencia_unidade=m["pen_resistencia_unidade"], contexto_umidade=m.get("pen_contexto_umidade") or "",
            medido_em=quando, chave_idempotencia=f"{chave}:pen:{m['pen_repeticao']}", **base))
    return [ItemSincronizacao.de_registro(r, "CRIAR") for r in registros]
