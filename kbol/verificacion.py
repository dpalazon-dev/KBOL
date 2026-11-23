"""Error común de los verificadores de aprobaciones, sea cual sea su canal (GitHub, declarado)."""

import json


def clave_de_revision(revision):
    """Forma canónica de una revisión para reconocerla repetida, aunque sus mapas anidados cambien de orden."""
    return json.dumps(revision, sort_keys=True, ensure_ascii=False, default=repr)


class ErrorDeVerificacion(Exception):
    def __init__(self, motivo, codigo="AUTORIDAD_INSUFICIENTE"):
        super().__init__(motivo)
        self.codigo = codigo
