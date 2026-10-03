"""Validação de anexos: tipo real pela assinatura do arquivo, tamanho e SHA-256.

O hash prova apenas que o arquivo não mudou desde o registro; não é prova material
absoluta. Metadados EXIF/GPS são declarações do dispositivo, não verdade.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from .. import config
from .problemas import Problema, erro

ASSINATURAS = (
    (b"\xff\xd8\xff", "image/jpeg", {".jpg", ".jpeg"}),
    (b"\x89PNG\r\n\x1a\n", "image/png", {".png"}),
    (b"%PDF-", "application/pdf", {".pdf"}),
)


@dataclass
class ResultadoAnexo:
    sha256: str
    tamanho_bytes: int
    tipo_detectado: str | None
    problemas: list[Problema] = field(default_factory=list)

    @property
    def aceito(self) -> bool:
        return not self.problemas


def detectar_tipo(conteudo: bytes) -> tuple[str | None, set[str]]:
    for assinatura, mime, extensoes in ASSINATURAS:
        if conteudo.startswith(assinatura):
            return mime, extensoes
    return None, set()


def validar_anexo(conteudo: bytes, nome_arquivo: str, tipo_declarado: str) -> ResultadoAnexo:
    sha = hashlib.sha256(conteudo).hexdigest()
    tamanho = len(conteudo)
    problemas: list[Problema] = []
    tipo, extensoes = detectar_tipo(conteudo)
    if tamanho == 0:
        problemas.append(erro("ANEXO_VAZIO", "arquivo", "arquivo vazio"))
    if tamanho > int(config.parametro("anexo_tamanho_maximo_bytes")):
        problemas.append(erro("ANEXO_GRANDE", "arquivo", f"arquivo com {tamanho} bytes excede o limite"))
    permitidos = set(config.parametro("anexo_tipos_permitidos"))
    if tipo is None or tipo not in permitidos:
        problemas.append(erro("ANEXO_TIPO_NAO_PERMITIDO", "arquivo",
                              "conteúdo não corresponde a JPEG, PNG ou PDF"))
    else:
        if (tipo_declarado or "").lower() != tipo:
            problemas.append(erro("ANEXO_TIPO_DIVERGENTE", "tipo_mime",
                                  f"declarado '{tipo_declarado}', conteúdo é '{tipo}'"))
        ext = "." + nome_arquivo.rsplit(".", 1)[-1].lower() if "." in nome_arquivo else ""
        if ext not in extensoes:
            problemas.append(erro("ANEXO_EXTENSAO_DIVERGENTE", "nome_arquivo",
                                  f"extensão '{ext}' não corresponde a '{tipo}'"))
    if "/" in nome_arquivo or "\\" in nome_arquivo or nome_arquivo.startswith("."):
        problemas.append(erro("ANEXO_NOME_INSEGURO", "nome_arquivo", "nome de arquivo com caminho"))
    return ResultadoAnexo(sha, tamanho, tipo, problemas)
