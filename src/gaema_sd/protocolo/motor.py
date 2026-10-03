"""Motor de protocolo: função pura, determinística e explicável.

Entrada: definição do protocolo + "fotografia" canônica das entradas de campo.
Saída: hash das entradas, regras disparadas / não disparadas / não avaliáveis por
ponto, categoria descritiva por ponto (só no protótipo), resumo descritivo,
limitações e hipóteses alternativas.

O motor não aplica nenhum limiar numérico e não agrega categoria para a área
inteira (agregação seria regra inventada). Estatísticas da penetrometria são
descritivas (contagem, mínimo, máximo, média aritmética), sem interpretação.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Iterable, Optional

from .. import config
from ..dominio import entidades as E
from ..dominio.enums import ModoProtocolo, VariavelCampo
from ..dominio.serializacao import json_canonico, para_dict, sha256_texto
from ..validacao import unidades
from .definicao import Condicao, DefinicaoProtocolo, Regra

NAO_CLASSIFICADO = "NÃO CLASSIFICADO"
EROSOES = ("EROSAO_LAMINAR", "SULCOS", "RAVINAS", "VOCOROCAS")
_PRESENCA = {"sim": True, "não": False, "nao": False}
METODO_PENETROMETRIA = ("Estatística descritiva por profundidade: número de repetições, mínimo, máximo e média "
                        "aritmética simples, após conversão das unidades para kPa. Nenhum limiar aplicado.")


# ------------------------------------------------------------------ entradas


def entradas_de(pontos: Iterable[E.PontoAmostral], observacoes: Iterable[E.Observacao],
                medicoes: Iterable[E.MedicaoPenetracao], evidencias: Iterable[E.Evidencia]) -> dict:
    """Fotografia canônica: conteúdo de campo e parâmetros usados, sem datas de gravação nem versão do registro."""

    def ordenar(itens):
        return sorted(itens, key=lambda x: x["id"])

    return {
        "parametros": {"gps_precisao_maxima_m": config.parametro("gps_precisao_maxima_m")},
        "pontos": ordenar({"id": p.id, "codigo": p.codigo, "latitude": float(p.latitude),
                           "longitude": float(p.longitude),
                           "precisao_gps_m": None if p.precisao_gps_m is None else float(p.precisao_gps_m),
                           "capturado_em": p.capturado_em.isoformat()} for p in pontos),
        "observacoes": ordenar({"id": o.id, "ponto_id": o.ponto_id, "variavel": o.variavel.value,
                                "valor_bruto": o.valor_bruto, "unidade_bruta": o.unidade_bruta,
                                "nota": o.nota} for o in observacoes),
        "medicoes": ordenar({"id": m.id, "ponto_id": m.ponto_id, "repeticao": m.repeticao,
                             "profundidade_bruta": m.profundidade_bruta,
                             "profundidade_unidade": m.profundidade_unidade,
                             "resistencia_bruta": m.resistencia_bruta, "resistencia_unidade": m.resistencia_unidade,
                             "contexto_umidade": m.contexto_umidade} for m in medicoes),
        "evidencias": ordenar({"id": e.id, "ponto_id": e.ponto_id, "observacao_id": e.observacao_id,
                               "categoria": e.categoria.value, "sha256": e.sha256} for e in evidencias),
    }


def normalizar(entradas: dict) -> dict:
    """Ordena cada lista por id: a ordem de chegada não altera hash nem resultado."""
    return {k: sorted(v, key=lambda x: x["id"]) if isinstance(v, list) else v for k, v in entradas.items()}


def hash_entradas(entradas: dict) -> str:
    return sha256_texto(json_canonico(normalizar(entradas)))


# ------------------------------------------------------------------ resultado


@dataclass
class ResultadoPonto:
    ponto_id: str
    codigo: str
    categoria: str = ""
    disparadas: list[str] = field(default_factory=list)
    nao_disparadas: list[str] = field(default_factory=list)
    nao_avaliaveis: list[tuple[str, str]] = field(default_factory=list)  # (regra, motivo)


@dataclass
class ResultadoMotor:
    codigo_protocolo: str
    versao_protocolo: str
    modo: ModoProtocolo
    rotulo: str
    hash_definicao: str
    hash_entradas: str
    por_ponto: list[ResultadoPonto]
    contagem_categorias: dict[str, int]
    resumo_variaveis: dict[str, dict[str, int]]
    penetrometria: list[dict]
    limitacoes: list[str]
    hipoteses_alternativas: list[str]

    @property
    def regras_disparadas(self) -> list[str]:
        return [f"{p.codigo}:{r}" for p in self.por_ponto for r in p.disparadas]

    @property
    def categoria_resumo(self) -> str:
        if self.modo is not ModoProtocolo.PROTOTIPO_TESTE:
            return ""
        return "; ".join(f"{c}: {n} ponto(s)" for c, n in sorted(self.contagem_categorias.items()))

    def texto_descritivo(self) -> str:
        linhas = [f"Protocolo {self.codigo_protocolo} {self.versao_protocolo} (modo {self.modo.value})."]
        if self.rotulo:
            linhas.append(self.rotulo + ".")
        linhas.append(f"Pontos amostrais avaliados: {len(self.por_ponto)}.")
        for var, cont in sorted(self.resumo_variaveis.items()):
            partes = ", ".join(f"{k}: {v}" for k, v in sorted(cont.items()))
            linhas.append(f"{var}: {partes}.")
        for p in self.por_ponto:
            if self.modo is ModoProtocolo.PROTOTIPO_TESTE:
                linhas.append(f"Ponto {p.codigo}: {p.categoria}; regras disparadas: "
                              f"{', '.join(p.disparadas) or 'nenhuma'}.")
        for pen in self.penetrometria:
            linhas.append(f"Penetrometria no ponto {pen['ponto']} a {pen['profundidade_cm']:g} cm: "
                          f"{pen['n']} repetição(ões), mín. {pen['min_kpa']:g} kPa, máx. {pen['max_kpa']:g} kPa, "
                          f"média {pen['media_kpa']:g} kPa.")
        return "\n".join(linhas)

    def como_dict(self) -> dict:
        d = para_dict(self)
        d["regras_disparadas"] = self.regras_disparadas
        return d


# ------------------------------------------------------------------ avaliação


def _estado_presenca(obs: list[dict]) -> tuple[Optional[bool], str]:
    """(True/False, '') ou (None, motivo) para uma variável num ponto."""
    if not obs:
        return None, "sem observação registrada"
    if any(o["unidade_bruta"].strip().lower() != "presenca" for o in obs):
        return None, "registrada em unidade diferente de 'presenca'"
    valores = {_PRESENCA.get(o["valor_bruto"].strip().lower()) for o in obs}
    if None in valores:
        return None, "valor de presença inválido"
    if len(valores) > 1:
        return None, "observações conflitantes no mesmo ponto"
    return valores.pop(), ""


def _avaliar_condicao(c: Condicao, estados: dict[str, tuple[Optional[bool], str]]):
    if c.operador in ("presente", "ausente"):
        v = c.variaveis[0]
        estado, motivo = estados[v]
        if estado is None:
            return None, f"{v}: {motivo}"
        return (estado if c.operador == "presente" else not estado), ""
    # qualquer_presente
    resultados = [estados[v] for v in c.variaveis]
    if any(e is True for e, _ in resultados):
        return True, ""
    if all(e is False for e, _ in resultados):
        return False, ""
    faltam = [f"{v}: {m}" for v, (e, m) in zip(c.variaveis, resultados) if e is None]
    return None, "; ".join(faltam)


def _avaliar_regra(r: Regra, estados) -> tuple[Optional[bool], str]:
    motivos, algum_falso = [], False
    for c in r.condicoes:
        valor, motivo = _avaliar_condicao(c, estados)
        if valor is False:
            algum_falso = True
        elif valor is None:
            motivos.append(motivo)
    if algum_falso:
        return False, ""
    if motivos:
        return None, "; ".join(motivos)
    return True, ""


def avaliar(definicao: DefinicaoProtocolo, hash_definicao: str, entradas: dict) -> ResultadoMotor:
    entradas = normalizar(entradas)
    obs_por_ponto: dict[str, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
    for o in entradas["observacoes"]:
        obs_por_ponto[o["ponto_id"]][o["variavel"]].append(o)

    variaveis_regras = sorted({v for r in definicao.regras for c in r.condicoes for v in c.variaveis})
    resumo: dict[str, Counter] = defaultdict(Counter)
    por_ponto: list[ResultadoPonto] = []
    for p in sorted(entradas["pontos"], key=lambda x: (x["codigo"], x["id"])):
        rp = ResultadoPonto(p["id"], p["codigo"])
        obs = obs_por_ponto[p["id"]]
        for var, lista in obs.items():
            estado, _ = _estado_presenca(lista)
            if estado is None and lista and lista[0]["unidade_bruta"].strip().lower() != "presenca":
                resumo[var]["registrado em outra unidade"] += 1
            else:
                resumo[var]["presente" if estado else "ausente" if estado is False else "indeterminado"] += 1
        if definicao.modo is ModoProtocolo.PROTOTIPO_TESTE:
            estados = {v: _estado_presenca(obs.get(v, [])) for v in variaveis_regras}
            for r in definicao.regras:
                valor, motivo = _avaliar_regra(r, estados)
                if valor is True:
                    rp.disparadas.append(r.id)
                elif valor is False:
                    rp.nao_disparadas.append(r.id)
                else:
                    rp.nao_avaliaveis.append((r.id, motivo))
            cats = sorted({r.categoria for r in definicao.regras if r.id in rp.disparadas})
            if len(cats) == 1:
                rp.categoria = cats[0]
            elif not cats:
                rp.categoria = NAO_CLASSIFICADO
            else:
                rp.categoria = f"{NAO_CLASSIFICADO} (categorias concorrentes: {', '.join(cats)})"
        por_ponto.append(rp)

    contagem = Counter(rp.categoria.split(" (")[0] if rp.categoria.startswith(NAO_CLASSIFICADO) else rp.categoria
                       for rp in por_ponto if rp.categoria)

    penetrometria = _penetrometria(entradas, {p["id"]: p["codigo"] for p in entradas["pontos"]})
    limitacoes = _limitacoes(definicao, entradas, por_ponto)
    hipoteses = [f"{_codigo(entradas, o['ponto_id'])}: {o['valor_bruto']}" + (f" ({o['nota']})" if o["nota"] else "")
                 for o in entradas["observacoes"] if o["variavel"] == VariavelCampo.HIPOTESE_ALTERNATIVA.value]

    return ResultadoMotor(
        codigo_protocolo=definicao.codigo, versao_protocolo=definicao.versao, modo=definicao.modo,
        rotulo=definicao.rotulo, hash_definicao=hash_definicao, hash_entradas=hash_entradas(entradas),
        por_ponto=por_ponto, contagem_categorias=dict(sorted(contagem.items())),
        resumo_variaveis={k: dict(sorted(v.items())) for k, v in sorted(resumo.items())},
        penetrometria=penetrometria, limitacoes=limitacoes, hipoteses_alternativas=hipoteses)


def _codigo(entradas: dict, ponto_id: str) -> str:
    return next((p["codigo"] for p in entradas["pontos"] if p["id"] == ponto_id), ponto_id)


def _penetrometria(entradas: dict, codigos: dict[str, str]) -> list[dict]:
    grupos: dict[tuple[str, float], list[float]] = defaultdict(list)
    for m in entradas["medicoes"]:
        prof, p1 = unidades.para_cm(m["profundidade_bruta"], m["profundidade_unidade"])
        res, p2 = unidades.para_kpa(m["resistencia_bruta"], m["resistencia_unidade"])
        if p1 or p2:
            continue  # inválidas não entram na estatística; a validação já as recusa na gravação
        grupos[(m["ponto_id"], round(prof, 6))].append(res)
    saida = []
    for (ponto_id, prof), valores in sorted(grupos.items(), key=lambda kv: (codigos.get(kv[0][0], ""), kv[0][1])):
        saida.append({"ponto": codigos.get(ponto_id, ponto_id), "profundidade_cm": prof, "n": len(valores),
                      "min_kpa": round(min(valores), 3), "max_kpa": round(max(valores), 3),
                      "media_kpa": round(sum(valores) / len(valores), 3), "metodo": METODO_PENETROMETRIA})
    return saida


def _limitacoes(definicao: DefinicaoProtocolo, entradas: dict, por_ponto: list[ResultadoPonto]) -> list[str]:
    lim = ["Resultado computado automaticamente: só tem valor técnico depois da revisão técnica humana.",
           "O sistema não conclui autoria, ilicitude, dano jurídico, responsabilidade nem nexo causal."]
    lim += list(definicao.limitacoes)
    limite = entradas["parametros"]["gps_precisao_maxima_m"]  # valor gravado na fotografia
    ruins = [p["codigo"] for p in entradas["pontos"]
             if limite is not None and (p["precisao_gps_m"] is None or p["precisao_gps_m"] > float(limite))]
    if ruins:
        lim.append(f"Precisão do GPS acima do limite operacional nos pontos: {', '.join(sorted(ruins))}.")
    nao_aval = sorted({p.codigo for p in por_ponto if p.nao_avaliaveis})
    if nao_aval:
        lim.append(f"Regras não avaliáveis por falta ou conflito de dados nos pontos: {', '.join(nao_aval)}.")
    if not entradas["medicoes"]:
        lim.append("Nenhuma medição de resistência à penetração registrada.")
    if not entradas["evidencias"]:
        lim.append("Nenhuma evidência fotográfica ou documental vinculada.")
    lim.append("Hash comprova integridade dos arquivos desde o registro; não é prova material absoluta. "
               "Data e coordenada de fotos são declarações do dispositivo.")
    return lim


def resultado_para_json(r: ResultadoMotor) -> str:
    return json.dumps(r.como_dict(), ensure_ascii=False, sort_keys=True, indent=2)
