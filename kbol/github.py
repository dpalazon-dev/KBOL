"""Verificador de aprobaciones por revisiones de pull request de GitHub.

Quien pide la integración solo identifica revisiones (`{mecanismo, pull, review_id}`); no aporta identidades, roles,
digests ni efectos. El verificador, con el repositorio fijado por configuración, comprueba en la API de GitHub que la
PR compara exactamente la base esperada con el commit propuesto y que la revisión está aprobada sobre ese commit, y
devuelve la cuenta que la hizo y su instante. Lo que la persona aprobó es ese diff, incluido el archivo de efectos
solicitados que viaja en él. No guarda tokens: el cliente lo toma de `KB_GITHUB_TOKEN`; sin él no está habilitado.
"""

import json
import os
import re

from .tiempo import es_instante, instante
from .verificacion import ErrorDeVerificacion  # noqa: F401 (se reexporta)

API = "https://api.github.com"
_REPO = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")


def _abridor_sin_redirecciones():
    """urllib reenvía Authorization al seguir una redirección: no se sigue ninguna. urllib.request se importa aquí y
    no al cargar el módulo, que la CLI importa en cada orden aunque no hable con GitHub."""
    import urllib.request

    class _SinRedirecciones(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None

    return urllib.request.build_opener(_SinRedirecciones)


class ClienteGitHub:
    """Cliente HTTP mínimo de la API REST de GitHub, de solo lectura y sin seguir redirecciones."""

    def __init__(self, token):
        self._token = token
        self._opener = _abridor_sin_redirecciones()

    def __repr__(self):
        return "ClienteGitHub(token=***)"

    @classmethod
    def desde_entorno(cls):
        token = os.environ.get("KB_GITHUB_TOKEN")
        if not token:
            raise ErrorDeVerificacion("verificador de GitHub no habilitado: falta KB_GITHUB_TOKEN")
        return cls(token)

    def get(self, ruta):
        import urllib.error
        import urllib.request

        peticion = urllib.request.Request(
            API + ruta,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self._token}",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "kbol",
            },
        )
        try:
            with self._opener.open(peticion, timeout=20) as respuesta:  # noqa: S310 - URL fija de la API
                return json.load(respuesta)
        except urllib.error.HTTPError as exc:
            codigo = "ACCESO_DENEGADO" if exc.code in (401, 403) else "AUTORIDAD_INSUFICIENTE"
            raise ErrorDeVerificacion(f"GitHub respondió {exc.code} para {ruta}", codigo) from None
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            raise ErrorDeVerificacion(
                f"GitHub no respondió de forma válida: {type(exc).__name__}", "RESULTADO_DESCONOCIDO"
            ) from None


def cuenta_autenticada(cliente):
    """{id, login} de la cuenta dueña del token del cliente, según GitHub (`GET /user`); solo cuentas de persona."""
    datos = cliente.get("/user")
    if not isinstance(datos, dict):
        raise ErrorDeVerificacion("respuesta inesperada de GitHub para /user")
    ident, login, tipo = datos.get("id"), datos.get("login"), datos.get("type")
    if not isinstance(ident, int) or isinstance(ident, bool) or not isinstance(login, str) or not login:
        raise ErrorDeVerificacion("GitHub no identificó la cuenta del token")
    if tipo != "User":
        raise ErrorDeVerificacion(f"la cuenta del token es de tipo {tipo!r}, no de una persona")
    return {"id": ident, "login": login}


class VerificadorGitHub:
    """Comprueba una revisión aprobada de una PR del repositorio configurado, sobre la base y el commit exactos."""

    mecanismo = "github-review"

    # Estados que fijan la postura de una cuenta; los comentarios no la cambian.
    EFECTIVOS = ("APPROVED", "CHANGES_REQUESTED", "DISMISSED")
    # Eventos que cambian lo que la PR compara después de aprobarla.
    CAMBIOS_DE_BASE = ("base_ref_changed", "base_ref_force_pushed")

    def __init__(self, cliente, repositorio, rama):
        if not isinstance(repositorio, str) or not _REPO.fullmatch(repositorio):
            raise ErrorDeVerificacion(f"repositorio de GitHub inválido: {repositorio!r}")
        if not isinstance(rama, str) or not rama:
            raise ErrorDeVerificacion("falta la rama canónica de la configuración")
        self.cliente = cliente
        self.repositorio = repositorio
        self.rama = rama

    def _paginas(self, ruta):
        elementos, pagina = [], 1
        while True:
            lote = self.cliente.get(f"{ruta}?per_page=100&page={pagina}")
            if not isinstance(lote, list):
                raise ErrorDeVerificacion(f"respuesta inesperada de GitHub para {ruta}")
            elementos += lote
            if len(lote) < 100:
                return elementos
            pagina += 1

    def verificar(self, revision, propuesta_rev, base_rev):
        """{identidad, instante, comprobante}; ErrorDeVerificacion si no acredita la aprobación de ese diff.

        Vale la postura vigente de la cuenta: su última revisión efectiva en la PR debe ser una aprobación del
        commit propuesto. Una aprobación que la misma persona retiró después no cuenta.
        """
        if not isinstance(revision, dict) or revision.get("mecanismo") != self.mecanismo:
            raise ErrorDeVerificacion("la referencia no es una revisión de GitHub")
        pull, review_id = revision.get("pull"), revision.get("review_id")
        if (
            not (isinstance(pull, int) and isinstance(review_id, int))
            or isinstance(pull, bool)
            or isinstance(review_id, bool)
        ):
            raise ErrorDeVerificacion("pull y review_id son enteros")
        pr = self.cliente.get(f"/repos/{self.repositorio}/pulls/{pull}")
        if (pr.get("head") or {}).get("sha") != propuesta_rev:
            raise ErrorDeVerificacion(
                "la PR ya no apunta al commit propuesto: se aprobó otro contenido", "APROBACION_CADUCADA"
            )
        if (pr.get("base") or {}).get("ref") != self.rama:
            raise ErrorDeVerificacion("la PR no apunta a la rama canónica")
        if (pr.get("base") or {}).get("sha") != base_rev:
            raise ErrorDeVerificacion("la PR no compara con la base esperada: lo revisado es otro diff")
        revisiones = self._paginas(f"/repos/{self.repositorio}/pulls/{pull}/reviews")
        rev = next((r for r in revisiones if r.get("id") == review_id), None)
        if rev is None:
            raise ErrorDeVerificacion("la revisión no existe en la PR")
        if rev.get("state") != "APPROVED":
            raise ErrorDeVerificacion(f"la revisión está en {rev.get('state')!r}, no aprobada")
        if rev.get("commit_id") != propuesta_rev:
            raise ErrorDeVerificacion(
                "la revisión aprueba otro commit: el contenido cambió después", "APROBACION_CADUCADA"
            )
        usuario = (rev.get("user") or {}).get("id")
        cuando = rev.get("submitted_at")
        if not isinstance(usuario, int) or isinstance(usuario, bool) or not es_instante(cuando):
            raise ErrorDeVerificacion("la revisión no identifica la cuenta o el instante")
        posturas = [
            r for r in revisiones if (r.get("user") or {}).get("id") == usuario and r.get("state") in self.EFECTIVOS
        ]
        ultima = posturas[-1] if posturas else None
        if ultima is None or ultima.get("state") != "APPROVED" or ultima.get("commit_id") != propuesta_rev:
            raise ErrorDeVerificacion(
                "la misma persona cambió o retiró su revisión después: su postura vigente no aprueba"
            )
        cronologia = self._paginas(f"/repos/{self.repositorio}/issues/{pull}/timeline")
        for ev in cronologia:
            if ev.get("event") in self.CAMBIOS_DE_BASE and (
                not es_instante(ev.get("created_at")) or instante(ev["created_at"]) >= instante(cuando)
            ):
                raise ErrorDeVerificacion("la base de la PR cambió después de la aprobación: lo aprobado era otro diff")
        comprobante = {
            "mecanismo": self.mecanismo,
            "repositorio": self.repositorio,
            "pull": pull,
            "review_id": review_id,
        }
        return {"identidad": f"github:{usuario}", "instante": cuando, "comprobante": comprobante}
