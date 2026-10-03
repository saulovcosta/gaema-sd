"""Validações do núcleo. Retornam listas de Problema (ERRO impede; ALERTA avisa)."""

from .problemas import Gravidade, Problema, exigir_sem_erros, tem_erro  # noqa: F401
