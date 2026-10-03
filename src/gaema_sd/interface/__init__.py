"""Interface local de operação (web), só para o computador de quem opera.

PROTÓTIPO com dados SINTÉTICOS: não há autenticação real (escolhe-se um usuário de teste), só atende em 127.0.0.1 e
não carrega nada de fora. Toda ação passa pelo `Nucleo` (acesso, validação, gravação, auditoria).
"""

from .app import Aplicacao, USUARIOS_DE_TESTE, servir

__all__ = ["Aplicacao", "USUARIOS_DE_TESTE", "servir"]
