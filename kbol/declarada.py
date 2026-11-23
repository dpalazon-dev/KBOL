"""Verificador de aprobaciones declaradas: la persona aprueba en una conversación y el agente cita sus palabras.

Mecanismo no conforme con KB-DPP (implementación, aprobación admitida): el comprobante no se contrasta con ninguna
identidad ni servicio de confianza, así que el verificador nunca lo da por autenticado y lo dice en el comprobante. Una
instalación solo lo habilita por decisión propia y declara en su matriz que la autenticidad de la aprobación no está
disponible (elecciones, «Mecanismos no conformes»).

Lo que sí se comprueba: la forma de la aprobación, que la base que se mostró precede a la base de la integración y,
en `autoridad.evaluar`, que los digests aprobados son los de lo que se integra. La persona, su naturaleza humana, su
actividad y su rol los comprueba `evaluar` contra la política base, como con cualquier canal.
"""

import hashlib
import re
import subprocess
from datetime import datetime, timedelta, timezone

from .digest import bytes_canonicos
from .snapshot import entorno_git
from .tiempo import es_instante, instante
from .verificacion import ErrorDeVerificacion

MECANISMO = "declarada"
_IDENTIDAD = re.compile(r"declarada:\S+")
_SHA = re.compile(r"[0-9a-f]{40}")
_DIGEST = re.compile(r"[0-9a-f]{64}")
CAMPOS = ("mecanismo", "identidad", "sesion", "instante", "cita", "base_mostrada", "digests")
MARGEN = timedelta(minutes=5)  # tolerancia de reloj entre quien registra y quien integra


def _texto(valor):
    return isinstance(valor, str) and valor.strip() != ""


class VerificadorDeclarado:
    mecanismo = MECANISMO

    def __init__(self, repo, ahora=None):
        """`repo` es el repositorio de la integración: sin él no se puede comprobar la base mostrada.

        `ahora` fija el reloj, para pruebas; por defecto, el del sistema.
        """
        if repo is None:
            raise ErrorDeVerificacion("el verificador declarado necesita el repositorio de la integración")
        self.repo = str(repo)
        self._ahora = ahora

    def verificar(self, revision, propuesta_rev, base_rev):
        """{identidad, instante, comprobante, digests, aprobacion_id}; ErrorDeVerificacion si no es válida."""
        if not isinstance(revision, dict) or revision.get("mecanismo") != MECANISMO:
            raise ErrorDeVerificacion("la referencia no es una aprobación declarada")
        if set(revision) != set(CAMPOS):
            raise ErrorDeVerificacion(f"una aprobación declarada lleva exactamente {', '.join(CAMPOS)}")
        identidad, sesion, cuando, cita = (revision[k] for k in ("identidad", "sesion", "instante", "cita"))
        base_mostrada, digests = revision["base_mostrada"], revision["digests"]
        if not isinstance(identidad, str) or not _IDENTIDAD.fullmatch(identidad):
            raise ErrorDeVerificacion("la identidad declarada tiene la forma declarada:<alias>")
        if not _texto(sesion) or not _texto(cita):
            raise ErrorDeVerificacion("una aprobación declarada necesita la sesión y la cita literal de la persona")
        if not es_instante(cuando):
            raise ErrorDeVerificacion("el instante de la aprobación es un instante ISO 8601 con zona")
        reloj = instante(self._ahora) if self._ahora else datetime.now(timezone.utc)
        if instante(cuando) > reloj + MARGEN:
            raise ErrorDeVerificacion("el instante de la aprobación está en el futuro")
        if not isinstance(base_mostrada, str) or not _SHA.fullmatch(base_mostrada):
            raise ErrorDeVerificacion("base_mostrada es el SHA completo de la base que se mostró")
        if not isinstance(digests, dict) or not all(
            isinstance(k, str) and isinstance(v, str) and _DIGEST.fullmatch(v) for k, v in digests.items()
        ):
            raise ErrorDeVerificacion("digests es un mapa ID → digest SHA-256 de lo que se mostró")
        if not self._precede(base_mostrada, base_rev):
            raise ErrorDeVerificacion("la base que se mostró no precede a la base de la integración")
        firmado = {k: revision[k] for k in CAMPOS}
        aprobacion_id = f"{MECANISMO}:{hashlib.sha256(bytes_canonicos(firmado)).hexdigest()[:16]}"
        comprobante = {
            "mecanismo": MECANISMO,
            "sesion": sesion,
            "instante": cuando,
            "cita": cita,
            "base_mostrada": base_mostrada,
            "digests": dict(digests),
            "autenticada": False,
            "resumen": f"{sesion}, {cuando}: «{cita}» (declarada, sin autenticar)",
        }
        return {
            "identidad": identidad,
            "instante": cuando,
            "comprobante": comprobante,
            "digests": dict(digests),
            "aprobacion_id": aprobacion_id,
        }

    def _precede(self, anterior, posterior):
        p = subprocess.run(
            ["git", "-C", self.repo, "merge-base", "--is-ancestor", anterior, posterior],
            capture_output=True,
            env=entorno_git(),
        )
        return p.returncode == 0
