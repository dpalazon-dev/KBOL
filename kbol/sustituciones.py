"""Sustituciones no declaradas: registros que dicen sustituir o derogar a otro sin declararlo (P04 del banco).

KBOL solo sigue `modifica` y `deja_obsoleta` para decidir qué rige. Un registro heredado puede decir en prosa que
sustituye a otro («Supersedes (partial): ADR-0005») o apuntarlo en `afecta_a`, y entonces el sustituido sale vigente
entero. Este módulo lo detecta de forma determinista y lo señala; no bloquea ni cambia la vigencia, que sigue
saliendo de lo declarado.

Hay indicio cuando, para un destino que existe en la base, que el registro podría haber declarado (`modifica` entre
decisiones, `deja_obsoleta` entre registros del mismo tipo) y que no declara:

- una línea del título, la descripción o el cuerpo nombra el destino poco después de un verbo de sustitución afirmado
  y en activa («sustituye», «supersedes», «deroga», «replaces», «deja obsoleta»), fuera de una pregunta; «sustituida
  por X» no cuenta, porque X es quien sustituye; o
- el destino está en `afecta_a` y alguna línea empieza por una etiqueta de sustitución («Supersedes», «Sustituye
  a», «Deroga», «Replaces», «Deja obsoleta»), aunque no lo nombre.

Un destino que otro registro ya regulariza (lo declara en `modifica` o `deja_obsoleta` y nombra al que avisa) no se
señala. Una negación justo antes del verbo («no sustituye») no cuenta. Es una heurística léxica: puede haber falsos
positivos y omisiones, y el aviso lo dice.
"""

import re

_VERBO = re.compile(
    r"(?<![\w-])(no\s+|not\s+|sin\s+)?"
    r"(supersed\w*|sustitu\w*|derog\w*|replac\w*|reemplaz\w*|deja\s+obsolet\w*|dejan\s+obsolet\w*)",
    re.IGNORECASE,
)
_ETIQUETA = re.compile(
    r"^\s*(?:[*>-]\s*)*(?:\*\*)?(supersedes|superseded|sustituye(?:\s+a)?|deroga|replaces|reemplaza|deja\s+obsoleta)\b",
    re.IGNORECASE,
)
_ID = re.compile(r"\b[A-Z][A-Z0-9]*-[0-9A-Za-z][0-9A-Za-z-]*")
_ARCHIVO = re.compile(r"\b(\d{4})-[\w.-]+\.md\b")


_PASIVA = re.compile(r"^\s*(?:\(?(?:en parte|partially|partial)\)?\s+)?(?:by|por)\b", re.IGNORECASE)
_VENTANA = 80


def _tras_el_verbo(linea):
    """Lo que sigue, hasta `_VENTANA` caracteres, a cada verbo de sustitución afirmado y en activa de la línea: ahí
    se nombra lo sustituido. «Sustituida por X» dice quién sustituye al registro, no a quién sustituye él."""
    trozos = []
    for m in _VERBO.finditer(linea):
        resto = linea[m.end() :]
        if m.group(1) or _PASIVA.match(resto):
            continue
        trozos.append(resto[:_VENTANA])
    return " ".join(trozos)


def _verbo_afirmado(texto):
    return next((m.group(2) for m in _VERBO.finditer(texto) if not m.group(1)), None)


class _Resolutor:
    """De una mención en prosa a un ID de la base: ID completo, prefijo único o archivo `NNNN-…md` de una ADR."""

    def __init__(self, snapshot):
        self.ids = set(snapshot.registros)
        self.por_numero = {}
        for i in self.ids:
            m = re.fullmatch(r"[A-Z]+-(\d{4})", i)
            if m:
                self.por_numero.setdefault(m.group(1), []).append(i)

    def __call__(self, token):
        token = token.rstrip("-.")
        if token in self.ids:
            return token
        if len(token) >= 6:
            hallados = [i for i in self.ids if i.startswith(token)]
            if len(hallados) == 1:
                return hallados[0]
        return None

    def en(self, linea):
        hallados = [x for x in (self(t) for t in _ID.findall(linea)) if x]
        for numero in _ARCHIVO.findall(linea):
            if len(self.por_numero.get(numero, [])) == 1:
                hallados.append(self.por_numero[numero][0])
        return list(dict.fromkeys(hallados))


def _declarados(r):
    destinos = {str(m.get("destino", "")).split("#", 1)[0] for m in r.get("modifica") or [] if isinstance(m, dict)}
    return destinos | set(r.get("deja_obsoleta") or [])


def _admisible(snapshot, ident, destino):
    """El registro podría haberlo declarado: `modifica` entre decisiones o `deja_obsoleta` entre registros del mismo
    tipo (decisión, hecho o fuente). Una pregunta que habla de sustituir no sustituye nada."""
    origen = snapshot.registros[ident].get("type")
    tipo = (snapshot.registros.get(destino) or {}).get("type")
    return origen in ("decision", "hecho", "fuente") and tipo == origen


def no_declaradas(snapshot):
    """Indicios [{registro, destino, indicio, motivo}] ordenados por registro y destino."""
    resolver = _Resolutor(snapshot)
    hallazgos = {}
    for ident, r in sorted(snapshot.registros.items()):
        cuerpo = snapshot.cuerpos.get(ident) or ""
        declarados = _declarados(r) | {ident}
        lineas = [r.get("title") or "", r.get("description") or ""] + cuerpo.splitlines()
        etiquetas = [x for x in lineas if _ETIQUETA.match(x)]
        # Líneas que afirman una sustitución: una etiqueta, o un verbo de sustitución afirmado fuera de una pregunta.
        afirman = [x for x in lineas if _ETIQUETA.match(x) or ("¿" not in x and "?" not in x and _tras_el_verbo(x))]
        candidatos = {}
        for linea in afirman:
            for destino in resolver.en(linea if _ETIQUETA.match(linea) else _tras_el_verbo(linea)):
                candidatos.setdefault(destino, f"«{' '.join(linea.split())[:160]}»")
        if etiquetas:
            for destino in r.get("afecta_a") or []:
                etiqueta = " ".join(etiquetas[0].split())[:160]
                candidatos.setdefault(destino, f"afecta_a y «{etiqueta}»")
        for destino, indicio in candidatos.items():
            if destino not in declarados and destino in snapshot.registros and _admisible(snapshot, ident, destino):
                hallazgos[(ident, destino)] = indicio
    regularizados = set()
    for otro, r in snapshot.registros.items():
        texto = f"{snapshot.cuerpos.get(otro) or ''} {r.get('title') or ''} {r.get('basada_en') or ''}"
        texto += f" {r.get('afecta_a') or ''} {r.get('depende_de') or ''}"
        for destino in _declarados(r):
            for ident, d in hallazgos:
                if d == destino and ident != otro and ident in texto:
                    regularizados.add((ident, d))
    return [
        {
            "registro": ident,
            "destino": destino,
            "indicio": indicio,
            "motivo": (
                f"SUSTITUCION_NO_DECLARADA: {ident} dice sustituir o derogar a {destino} ({indicio}) sin declararlo "
                f"en modifica ni en deja_obsoleta; la vigencia de {destino} se calcula como si no lo hiciera "
                "(indicio léxico: compruébalo en el texto)"
            ),
        }
        for (ident, destino), indicio in sorted(hallazgos.items())
        if (ident, destino) not in regularizados
    ]


def avisos_para(indicios, ids):
    """Los motivos de los indicios que afectan a `ids`, como registro que avisa o como destino."""
    ids = set(ids)
    return [i["motivo"] for i in indicios if i["registro"] in ids or i["destino"] in ids]
