import pytest

from gaema_sd.acesso import Ator
from gaema_sd.dominio.enums import Papel
from gaema_sd.nucleo import Nucleo
from gaema_sd.persistencia import Repositorio
from gaema_sd.sinteticos import cenario as _cenario

P = Papel


@pytest.fixture
def atores():
    return {
        "analista": Ator.de("usuario-sintetico-10", P.ANALISTA_TRIAGEM),
        "coord": Ator.de("usuario-sintetico-03", P.COORDENADOR),
        "tecnico": Ator.de("usuario-sintetico-02", P.TECNICO_CAMPO),
        "revisor": Ator.de("usuario-sintetico-04", P.REVISOR_TECNICO),
        "membro": Ator.de("usuario-sintetico-05", P.MEMBRO_MP),
        "auditor": Ator.de("usuario-sintetico-06", P.AUDITOR),
        "admin": Ator.de("usuario-sintetico-07", P.ADMINISTRADOR),
        "sistema": Ator.de("processo-sintetico", P.SISTEMA),
    }


@pytest.fixture
def cenario():
    return _cenario()


@pytest.fixture
def nucleo():
    repo = Repositorio(":memory:")
    yield Nucleo(repo)
    repo.fechar()
