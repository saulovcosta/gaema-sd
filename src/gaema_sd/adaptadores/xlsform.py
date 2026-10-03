"""XLSForm do formulário de vistoria, GERADO do domínio (sem valores inventados).

Uma submissão = um ponto amostral. Presença/ausência não é obrigatória: o campo em branco significa "não observado"
(o motor trata a falta de observação como regra não avaliável). Nenhum campo tem valor padrão. Só repetições de um nível (sem repetição aninhada), porque o
comportamento de repetições aninhadas no Survey123 não foi verificado. Nada aqui define limiar,
profundidade padrão ou número mínimo de repetições (LA-04); GPS ruim gera alerta no núcleo, não bloqueio.

NÃO FOI VERIFICADO: abertura no Survey123 Connect, publicação, uso offline em aparelho, mapa base.
A conferência feita é estrutural (testes) e de sintaxe XLSForm/ODK com pyxform.

Uso: python -m gaema_sd.adaptadores.xlsform escrever DESTINO.xlsx
"""

from __future__ import annotations

import csv
import hashlib
import io
import sys
from pathlib import Path

from ..dominio import entidades as E
from ..dominio.enums import CategoriaEvidencia, CondicaoAcesso, VariavelCampo
from ..validacao.unidades import PARA_CM, PARA_KPA

V = VariavelCampo
COLUNAS_SURVEY = ["type", "name", "label", "hint", "required", "relevant", "constraint", "constraint_message",
                  "default", "appearance"]
COLUNAS_CHOICES = ["list_name", "name", "label"]

# As 7 variáveis que o protótipo avalia por presença/ausência (config/protocolos/gaema-prototipo-teste-0.1.0.json).
VARIAVEIS_PRESENCA = (V.PLANTAS_INVASORAS, V.CUPINS_MONTICULO, V.EROSAO_LAMINAR, V.SULCOS, V.RAVINAS,
                      V.VOCOROCAS, V.SOLO_EXPOSTO)

ROTULO_VARIAVEL = {
    V.COBERTURA_FORRAGEIRA: "Cobertura forrageira", V.VIGOR_FORRAGEIRA: "Vigor da forrageira",
    V.ALTURA_PASTO: "Altura do pasto", V.SOLO_EXPOSTO: "Solo exposto", V.PLANTAS_INVASORAS: "Plantas invasoras",
    V.CUPINS_MONTICULO: "Cupins (montículo)", V.EROSAO_LAMINAR: "Erosão laminar", V.SULCOS: "Sulcos",
    V.RAVINAS: "Ravinas", V.VOCOROCAS: "Voçorocas", V.UMIDADE_SOLO: "Umidade do solo",
    V.PRECIPITACAO_RECENTE: "Precipitação recente", V.TIPO_SOLO: "Tipo de solo",
    V.FORMACAO_GEOLOGICA: "Formação geológica", V.ANIMAIS_PASTEJO: "Animais em pastejo",
    V.CONTEXTO_SAZONAL: "Contexto sazonal", V.DRENAGEM: "Drenagem", V.DECLIVIDADE: "Declividade",
    V.MANEJO_INFORMADO: "Manejo informado", V.HIPOTESE_ALTERNATIVA: "Hipótese alternativa", V.OUTRA: "Outra",
}
ROTULO_ACESSO = {CondicaoAcesso.NAO_INFORMADA: "Não informada", CondicaoAcesso.ACESSO_REALIZADO: "Acesso realizado",
                 CondicaoAcesso.ACESSO_PARCIAL: "Acesso parcial", CondicaoAcesso.SEM_ACESSO: "Sem acesso"}
ROTULO_EVIDENCIA = {
    CategoriaEvidencia.FOTO_PANORAMICA: "Foto panorâmica", CategoriaEvidencia.FOTO_SOLO: "Foto do solo",
    CategoriaEvidencia.FOTO_FORRAGEIRA: "Foto da forrageira", CategoriaEvidencia.FOTO_INVASORA: "Foto de invasora",
    CategoriaEvidencia.FOTO_CUPINZEIRO: "Foto de cupinzeiro", CategoriaEvidencia.FOTO_EROSAO: "Foto de erosão",
    CategoriaEvidencia.FOTO_MEDICAO: "Foto da medição", CategoriaEvidencia.DOCUMENTO: "Documento",
    CategoriaEvidencia.OUTRA: "Outra",
}
ROTULO_UNIDADE = {"kpa": "kPa", "mpa": "MPa", "kgf/cm2": "kgf/cm²", "kgf/cm²": None, "cm": "cm", "mm": "mm", "m": "m"}


def nome_presenca(v: VariavelCampo) -> str:
    return "presenca_" + v.value.lower()


def _linha(**campos) -> dict:
    return {c: campos.get(c, "") for c in COLUNAS_SURVEY}


def survey() -> list[dict]:
    L = _linha
    s = [
        L(type="begin_group", name="identificacao", label="Identificação da vistoria"),
        L(type="text", name="campanha_id", label="Identificador da campanha", required="yes",
          hint="Fornecido pela coordenação; ver missão baixada."),
        L(type="text", name="dispositivo_id", label="Identificação do aparelho", required="yes"),
        L(type="text", name="observador_id", label="Identificador de quem coleta", required="yes"),
        L(type="dateTime", name="capturado_em", label="Data e hora da coleta", required="yes",
          hint="Informe quando o ponto foi coletado; o formulário não assume a hora de abertura."),
        L(type="select_one condicao_acesso", name="condicao_acesso", label="Condição de acesso à área",
          required="yes"),
        L(type="text", name="nota_acesso", label="Nota sobre o acesso", relevant="${condicao_acesso} = 'SEM_ACESSO'",
          required="${condicao_acesso} = 'SEM_ACESSO'", hint="Obrigatória quando não houve acesso."),
        L(type="end_group", name="identificacao"),
        L(type="begin_group", name="ponto", label="Ponto amostral"),
        L(type="text", name="codigo_ponto", label="Código do ponto", required="yes"),
        L(type="geopoint", name="localizacao", label="Localização (GPS)", required="yes",
          hint="O núcleo registra a precisão e alerta se for ruim; não bloqueia o registro."),
        L(type="end_group", name="ponto"),
        L(type="begin_group", name="presenca", label="Presença ou ausência"),
    ]
    for v in VARIAVEIS_PRESENCA:
        s.append(L(type="select_one sim_nao", name=nome_presenca(v), label=ROTULO_VARIAVEL[v],
                   hint="Deixe em branco se não foi observado: o sistema registra a falta como não avaliável.",
                   appearance="horizontal"))
    s += [
        L(type="end_group", name="presenca"),
        L(type="text", name="hipotese_alternativa", label="Hipótese alternativa (texto livre)",
          hint="Explicação alternativa que a equipe considere plausível."),
        L(type="begin_repeat", name="outras_observacoes", label="Outras observações"),
        L(type="select_one variavel_campo", name="outra_variavel", label="Variável", required="yes"),
        L(type="text", name="outra_valor_bruto", label="Valor, como observado", required="yes"),
        L(type="text", name="outra_unidade_bruta", label="Unidade", required="yes"),
        L(type="text", name="outra_nota", label="Nota", relevant="${outra_variavel} = 'OUTRA'",
          required="${outra_variavel} = 'OUTRA'", hint="Obrigatória para a variável 'Outra'."),
        L(type="end_repeat", name="outras_observacoes"),
        L(type="begin_repeat", name="penetrometria", label="Resistência à penetração"),
        L(type="integer", name="pen_repeticao", label="Repetição", required="yes", constraint=". >= 1",
          constraint_message="A repetição começa em 1."),
        L(type="decimal", name="pen_profundidade", label="Profundidade", required="yes", constraint=". >= 0",
          constraint_message="Não pode ser negativa."),
        L(type="select_one unidade_profundidade", name="pen_profundidade_unidade", label="Unidade da profundidade",
          required="yes"),
        L(type="decimal", name="pen_resistencia", label="Resistência", required="yes", constraint=". >= 0",
          constraint_message="Não pode ser negativa."),
        L(type="select_one unidade_resistencia", name="pen_resistencia_unidade", label="Unidade da resistência",
          required="yes"),
        L(type="text", name="pen_contexto_umidade", label="Contexto de umidade (texto livre)"),
        L(type="end_repeat", name="penetrometria"),
        L(type="begin_repeat", name="fotos", label="Fotos"),
        L(type="select_one categoria_evidencia", name="foto_categoria", label="Categoria da foto", required="yes"),
        L(type="image", name="foto_arquivo", label="Foto", required="yes"),
        L(type="end_repeat", name="fotos"),
    ]
    return s


def choices() -> list[dict]:
    c = [{"list_name": "sim_nao", "name": "sim", "label": "Sim"}, {"list_name": "sim_nao", "name": "nao", "label": "Não"}]
    c += [{"list_name": "condicao_acesso", "name": a.value, "label": ROTULO_ACESSO[a]} for a in CondicaoAcesso]
    c += [{"list_name": "variavel_campo", "name": v.value, "label": ROTULO_VARIAVEL[v]} for v in VariavelCampo]
    c += [{"list_name": "unidade_profundidade", "name": u, "label": ROTULO_UNIDADE[u]} for u in PARA_CM]
    c += [{"list_name": "unidade_resistencia", "name": u, "label": ROTULO_UNIDADE[u]}
          for u in PARA_KPA if ROTULO_UNIDADE[u]]   # "kgf/cm²" é sinônimo de "kgf/cm2": uma opção só
    c += [{"list_name": "categoria_evidencia", "name": k.value, "label": ROTULO_EVIDENCIA[k]}
          for k in CategoriaEvidencia]
    return c


def settings() -> list[dict]:
    corpo = _csv(survey(), COLUNAS_SURVEY) + _csv(choices(), COLUNAS_CHOICES)
    versao = hashlib.sha256(corpo.encode("utf-8")).hexdigest()[:12]
    return [{"form_title": "GAEMA SD - Vistoria de campo (modelo de teste, dados sintéticos)",
             "form_id": "gaema_sd_vistoria", "version": versao, "default_language": "portugues"}]


# nome no formulário → (entidade, campo do domínio, observação)
def mapeamento() -> list[dict]:
    m = [("campanha_id", "PontoAmostral", "campanha_id", ""), ("dispositivo_id", "PontoAmostral", "dispositivo_id", ""),
         ("observador_id", "Observacao", "observador_id", ""), ("capturado_em", "PontoAmostral", "capturado_em", ""),
         ("condicao_acesso", "CampanhaVistoria", "condicao_acesso", "campo da campanha; não é gravado por ponto"),
         ("nota_acesso", "CampanhaVistoria", "nota_acesso", "campo da campanha; não é gravado por ponto"),
         ("codigo_ponto", "PontoAmostral", "codigo", ""),
         ("localizacao", "PontoAmostral", "latitude", "ODK: 'lat lon altitude precisão'; ver latitude, longitude, altitude_m, precisao_gps_m")]
    m += [(nome_presenca(v), "Observacao", "valor_bruto", f"variavel={v.value}; unidade_bruta=presenca")
          for v in VARIAVEIS_PRESENCA]
    m += [("hipotese_alternativa", "Observacao", "valor_bruto", "variavel=HIPOTESE_ALTERNATIVA; unidade_bruta=texto"),
          ("outra_variavel", "Observacao", "variavel", ""), ("outra_valor_bruto", "Observacao", "valor_bruto", ""),
          ("outra_unidade_bruta", "Observacao", "unidade_bruta", ""), ("outra_nota", "Observacao", "nota", ""),
          ("pen_repeticao", "MedicaoPenetracao", "repeticao", ""),
          ("pen_profundidade", "MedicaoPenetracao", "profundidade_bruta", ""),
          ("pen_profundidade_unidade", "MedicaoPenetracao", "profundidade_unidade", ""),
          ("pen_resistencia", "MedicaoPenetracao", "resistencia_bruta", ""),
          ("pen_resistencia_unidade", "MedicaoPenetracao", "resistencia_unidade", ""),
          ("pen_contexto_umidade", "MedicaoPenetracao", "contexto_umidade", ""),
          ("foto_categoria", "Evidencia", "categoria", "o arquivo entra por Nucleo.registrar_evidencia, com hash"),
          ("foto_arquivo", "Evidencia", "armazenamento_ref", "anexo; não traduzido por traduzir_submissao")]
    return [{"campo_formulario": a, "entidade": b, "campo_dominio": c, "observacao": d} for a, b, c, d in m]


def classes_do_dominio() -> dict[str, type]:
    return {c.__name__: c for c in E.ENTIDADES}


def _csv(linhas: list[dict], colunas: list[str]) -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=colunas, lineterminator="\n")
    w.writeheader()
    w.writerows(linhas)
    return buf.getvalue()


def arquivos_csv() -> dict[str, str]:
    """Nome do arquivo → conteúdo. Gravados em adapters/arcgis/xlsform/ por scripts/gerar_contratos.py."""
    cfg = settings()
    return {"survey.csv": _csv(survey(), COLUNAS_SURVEY), "choices.csv": _csv(choices(), COLUNAS_CHOICES),
            "settings.csv": _csv(cfg, list(cfg[0])),
            "mapeamento.csv": _csv(mapeamento(), ["campo_formulario", "entidade", "campo_dominio", "observacao"])}


def escrever_xlsx(destino: str | Path) -> Path:
    """Grava o XLSForm em .xlsx (planilhas survey, choices e settings). Exige openpyxl."""
    from openpyxl import Workbook

    wb = Workbook()
    wb.remove(wb.active)
    cfg = settings()
    for nome, linhas, colunas in (("survey", survey(), COLUNAS_SURVEY), ("choices", choices(), COLUNAS_CHOICES),
                                  ("settings", cfg, list(cfg[0]))):
        ws = wb.create_sheet(nome)
        ws.append(colunas)
        for l in linhas:
            ws.append([l[c] for c in colunas])
    destino = Path(destino)
    wb.save(destino)
    return destino


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "escrever":
        print(f"gravado: {escrever_xlsx(sys.argv[2])}")
        sys.exit(0)
    print(__doc__)
    sys.exit(2)
