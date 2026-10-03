import hashlib

from gaema_sd.validacao.anexos import validar_anexo

JPEG = b"\xff\xd8\xff\xe0" + b"conteudo sintetico"
PNG = b"\x89PNG\r\n\x1a\n" + b"conteudo sintetico"
PDF = b"%PDF-1.7\n" + b"conteudo sintetico"


def cod(r):
    return {p.codigo for p in r.problemas}


def test_anexos_validos_com_hash():
    for conteudo, nome, mime in [(JPEG, "a.jpg", "image/jpeg"), (PNG, "b.PNG", "image/png"),
                                 (PDF, "c.pdf", "application/pdf")]:
        r = validar_anexo(conteudo, nome, mime)
        assert r.aceito, r.problemas
        assert r.sha256 == hashlib.sha256(conteudo).hexdigest()


def test_executavel_disfarcado_de_foto():
    r = validar_anexo(b"MZ\x90\x00programa", "foto.jpg", "image/jpeg")
    assert "ANEXO_TIPO_NAO_PERMITIDO" in cod(r)


def test_tipo_declarado_diverge_do_conteudo():
    assert "ANEXO_TIPO_DIVERGENTE" in cod(validar_anexo(PNG, "b.png", "image/jpeg"))
    assert "ANEXO_EXTENSAO_DIVERGENTE" in cod(validar_anexo(PNG, "b.jpg", "image/png"))


def test_arquivo_vazio_grande_ou_com_caminho():
    assert "ANEXO_VAZIO" in cod(validar_anexo(b"", "a.jpg", "image/jpeg"))
    grande = JPEG + b"\x00" * (25 * 1024 * 1024)
    assert "ANEXO_GRANDE" in cod(validar_anexo(grande, "a.jpg", "image/jpeg"))
    assert "ANEXO_NOME_INSEGURO" in cod(validar_anexo(JPEG, "../../etc/a.jpg", "image/jpeg"))


def test_um_byte_diferente_muda_o_hash():
    a = validar_anexo(JPEG, "a.jpg", "image/jpeg").sha256
    b = validar_anexo(JPEG[:-1] + b"X", "a.jpg", "image/jpeg").sha256
    assert a != b
