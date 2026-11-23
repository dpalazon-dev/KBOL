"""Contenedor canónico: archivo UTF-8 con cabecera YAML entre `---` y cuerpo Markdown.

La lectura es segura y no ejecuta nada: rechaza claves repetidas, claves no textuales, etiquetas explícitas,
anclas, alias y claves de fusión. Las fechas se leen como texto: su precisión la decide el esquema, no el parser.
La escritura canónica valida antes de escribir y rechaza campos que el esquema no declara.
"""

import os
import re
import tempfile
import uuid
from pathlib import Path

import yaml

from .modelo import PREFIJO

_DELIMITADO = re.compile(r"\A---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|\Z)", re.S)
_FUSION = "tag:yaml.org,2002:merge"


class ErrorDeFormato(ValueError):
    """Contenido que no es un contenedor canónico legible."""


class _Cargador(yaml.SafeLoader):
    def compose_node(self, parent, index):
        evento = self.peek_event()
        if isinstance(evento, yaml.AliasEvent) or getattr(evento, "anchor", None) is not None:
            raise ErrorDeFormato("anclas y alias no admitidos en la cabecera")
        if getattr(evento, "tag", None) is not None:
            raise ErrorDeFormato(f"etiqueta explícita no admitida: {evento.tag}")
        return super().compose_node(parent, index)


def _mapa(cargador, nodo, deep=False):
    resultado = {}
    for nodo_clave, nodo_valor in nodo.value:
        if nodo_clave.tag == _FUSION:
            raise ErrorDeFormato("claves de fusión no admitidas")
        clave = cargador.construct_object(nodo_clave, deep=True)
        if not isinstance(clave, str):
            raise ErrorDeFormato(f"clave no textual: {clave!r}")
        if clave in resultado:
            raise ErrorDeFormato(f"clave repetida: {clave}")
        resultado[clave] = cargador.construct_object(nodo_valor, deep=True)
    return resultado


_Cargador.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _mapa)
_Cargador.yaml_implicit_resolvers = {
    k: [(tag, rx) for tag, rx in v if tag != "tag:yaml.org,2002:timestamp"]
    for k, v in yaml.SafeLoader.yaml_implicit_resolvers.items()
}


def parse(texto):
    """Devuelve (cabecera, cuerpo). El cuerpo se devuelve tal cual, sin normalizar."""
    m = _DELIMITADO.match(texto)
    if not m:
        raise ErrorDeFormato("falta la cabecera YAML delimitada por ---")
    try:
        datos = yaml.load(m.group(1), Loader=_Cargador)  # noqa: S506 - cargador seguro propio
    except yaml.YAMLError as exc:
        raise ErrorDeFormato(str(exc)) from exc
    if not isinstance(datos, dict):
        raise ErrorDeFormato("la cabecera debe ser un mapa")
    return datos, texto[m.end() :]


def nuevo_id(tipo):
    """ID nuevo con prefijo de tipo y UUID v4 (contrato KB-DPP, «Identidad»)."""
    return f"{PREFIJO[tipo]}-{uuid.uuid4()}"


def normalizar_cuerpo(cuerpo):
    return cuerpo.replace("\r\n", "\n").replace("\r", "\n")


def serializar(registro, cuerpo, modo="propuesta"):
    """Texto en forma canónica de un registro válido en `modo` (`propuesta` o `canonico`).

    ErrorDeFormato si no valida o no sobrevive a la ida y vuelta. Nunca admite campos no declarados.
    """
    from .schema import validar

    if modo not in ("propuesta", "canonico"):
        raise ValueError("la escritura admite solo los modos propuesta y canonico")
    errores = [h for h in validar(registro, cuerpo, modo=modo) if h["severidad"] == "error"]
    if errores:
        raise ErrorDeFormato("ESQUEMA_INVALIDO: " + "; ".join(f"{h['ruta']}: {h['mensaje']}" for h in errores))
    cabecera = yaml.safe_dump(registro, allow_unicode=True, sort_keys=False, default_flow_style=False, width=10**9)
    texto = f"---\n{cabecera}---\n{normalizar_cuerpo(cuerpo)}"
    releido, cuerpo_releido = parse(texto)
    if releido != registro or cuerpo_releido != normalizar_cuerpo(cuerpo):
        raise ErrorDeFormato("la serialización no conserva el contenido")
    return texto


def escribir(ruta, registro, cuerpo, modo="propuesta"):
    """Escribe el registro de forma atómica. Escribir un archivo no acepta ni integra su contenido."""
    texto = serializar(registro, cuerpo, modo)
    ruta = Path(ruta)
    fd, tmp = tempfile.mkstemp(dir=ruta.parent, prefix=f".{ruta.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(texto)
        os.replace(tmp, ruta)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
