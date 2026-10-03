"""Erros do núcleo. Todo erro traz mensagem em português claro."""


class ErroGaema(Exception):
    """Base dos erros do GAEMA SD."""


class AcessoNegado(ErroGaema):
    """O ator não tem papel que permita a ação."""


class TransicaoInvalida(ErroGaema):
    """A mudança de estado não existe na tabela ou falhou em pré-condição."""


class ValidacaoFalhou(ErroGaema):
    """O registro tem problemas impeditivos."""

    def __init__(self, problemas):
        self.problemas = list(problemas)
        texto = "; ".join(f"{p.campo}: {p.mensagem}" for p in self.problemas)
        super().__init__(f"Validação falhou: {texto}")


class ConflitoAtualizacao(ErroGaema):
    """O registro foi alterado por outra pessoa depois de lido."""


class ConflitoIdempotencia(ErroGaema):
    """Mesma chave de envio com conteúdo diferente: não sobrescreve em silêncio."""


class RegistroNaoEncontrado(ErroGaema):
    """Identificador inexistente."""


class AuditoriaCorrompida(ErroGaema):
    """A cadeia de eventos de auditoria não confere."""
