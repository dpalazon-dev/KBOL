"""Búsqueda léxica: la «Exploración» del núcleo (§8), candidatos por texto libre o alias.

Encuentra registros y cláusulas que comparten términos con la consulta y los devuelve con su identidad, su estado, su
vigencia en los cortes y un fragmento. No decide qué rige: un candidato es un punto de partida para `consultar` o
`consolidar`, que son los que responden. Por defecto solo devuelve lo vigente; las propuestas y lo que no rige se
cuentan y solo se muestran si se piden, marcados.

Todo ocurre en memoria sobre el snapshot de la consulta, sin vectores ni índice persistente. La puntuación es BM25
sobre términos normalizados (minúsculas, sin tildes, prefijo de seis letras, sin palabras vacías), con el título y los
alias contados dos veces. Es determinista: a igual snapshot y consulta, igual orden.

Unidades: cada cláusula de una decisión es una (con el título y la descripción de su decisión); los demás registros,
una cada uno, con título, descripción, alias (`define`, `alias`), afirmación y cuerpo. Los registros heredados no se
examinan: lo dice la cobertura. Cada registro sale una vez, por su mejor unidad; las demás cláusulas que
coinciden van en `otras_anclas`.
"""

import math
import re
import unicodedata

from .consolidar import RIGE, _Consulta
from .markdown import ErrorDeMarca, clausulas
from .proyeccion import estado_al_corte
from .sustituciones import avisos_para, no_declaradas

CLASES = ("vigente", "propuesta", "no_vigente")
_PROPUESTAS = {"propuesta", "propuesto", "borrador"}
_NO_VIGENTES = {"rechazada", "retirada", "retirado", "descartada", "refutada", "cancelado", "cerrado"}
_VACIAS = set(
    ["a", "al", "algo", "como", "con", "cual", "cuales", "cuando", "cuanto", "cuantos", "cuantas", "de", "del", "donde", "el", "ella", "ellos", "en", "entre", "es", "esa", "ese", "eso", "esta", "este", "esto", "estos", "fue", "ha", "hay", "la", "las", "le", "lo", "los", "mas", "me", "mi", "mucho", "muy", "no", "nos", "o", "para", "pero", "por", "que", "quien", "se", "sea", "ser", "si", "sin", "sobre", "su", "sus", "tambien", "te", "tiene", "un", "una", "uno", "unos", "y", "ya", "hoy", "dice", "an", "and", "are", "as", "at", "be", "by", "for", "from", "has", "have", "how", "in", "is", "it", "its", "of", "on", "or", "that", "the", "this", "to", "was", "what", "when", "which", "who", "with"]
)
_K1, _B = 1.2, 0.75
_FRAGMENTO = 240


def _plano(texto):
    sin = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in sin if not unicodedata.combining(c)).lower()


def terminos(texto):
    """Términos normalizados de un texto, en orden y con repeticiones."""
    salida = []
    for t in re.findall(r"[a-z0-9]+", _plano(texto or "")):
        if len(t) < 2 or t in _VACIAS:
            continue
        salida.append(t[:6] if not t.isdigit() else t)
    return salida


def _alias(r):
    textos = list(r.get("alias") or []) + [r.get("nombre") or ""]
    for d in r.get("define") or []:
        if isinstance(d, dict):
            textos += [d.get("termino") or "", *(d.get("alias") or [])]
    return " ".join(t for t in textos if isinstance(t, str))


def _unidades(snapshot, avisar):
    """[(id, ancla, texto_ponderado, texto_visible)] de los registros canónicos."""
    unidades = []
    for ident, r in sorted(snapshot.registros.items()):
        cabecera = f"{r.get('title') or ''} {_alias(r)}"
        resto = f"{r.get('description') or ''}"
        cuerpo = snapshot.cuerpos.get(ident) or ""
        if r.get("type") == "decision":
            try:
                anclas = clausulas(cuerpo)
            except ErrorDeMarca as exc:
                avisar(f"{ident}: cuerpo mal formado ({exc}); se busca en su cabecera")
                anclas = {}
            for ancla, texto in anclas.items():
                unidades.append((ident, ancla, f"{cabecera} {cabecera} {resto} {texto}", texto))
            if anclas:
                continue
        visible = " ".join(str(x) for x in (r.get("afirmacion"), r.get("description"), cuerpo) if x)
        unidades.append((ident, None, f"{cabecera} {cabecera} {resto} {r.get('afirmacion') or ''} {cuerpo}", visible))
    return unidades


def _fragmento(visible, consulta):
    texto = " ".join(visible.split())
    plano = _plano(texto)
    pos = [plano.find(t) for t in consulta if plano.find(t) >= 0]
    inicio = max(0, min(pos) - 60) if pos else 0
    trozo = texto[inicio : inicio + _FRAGMENTO]
    return ("…" if inicio else "") + trozo + ("…" if inicio + _FRAGMENTO < len(texto) else "")


def _clase(consulta, snapshot, ident, ancla):
    """(clase, estado, vigencia, rige_ahora) de un candidato en los cortes."""
    r = snapshot.registros[ident]
    estado = estado_al_corte(r, consulta.conocido_hasta)
    if r.get("type") == "decision" and ancla:
        sit = consulta.situacion(ident)
        if sit != RIGE:
            clase = "propuesta" if consulta.es_propuesta(ident) else "no_vigente"
            return clase, estado, sit, None
        res = consulta.resolver(f"{ident}#{ancla}")
        if res["estado"] == "vigente" and res.get("origen") == res["referencia"]:
            return "vigente", estado, "vigente", None
        rige_ahora = res.get("origen") if res["estado"] == "vigente" else None
        return "no_vigente", estado, res["estado"] if res["estado"] != "vigente" else "sustituida", rige_ahora
    if estado is None:
        return "no_vigente", estado, "no_constaba", None
    if estado in _PROPUESTAS:
        return "propuesta", estado, "no_rige", None
    if estado in _NO_VIGENTES:
        return "no_vigente", estado, "no_rige", None
    return "vigente", estado, "vigente", None


def buscar(snapshot, texto, *, valido_en, conocido_hasta, incluir=(), limite=10):
    """{consulta, terminos, candidatos, excluidos, examinados, truncado, advertencias}."""
    consulta = _Consulta(snapshot, valido_en, conocido_hasta)
    q = list(dict.fromkeys(terminos(texto)))
    unidades = _unidades(snapshot, consulta.avisar)
    docs = [terminos(u[2]) for u in unidades]
    n = len(docs)
    media = (sum(len(d) for d in docs) / n) if n else 0
    df = {t: sum(1 for d in docs if t in d) for t in q}
    puntuadas = []
    for unidad, d in zip(unidades, docs):
        if not d:
            continue
        frecuencias = {t: d.count(t) for t in q if t in df and df[t]}
        puntos = 0.0
        for t, f in frecuencias.items():
            if not f:
                continue
            idf = math.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5))
            puntos += idf * f * (_K1 + 1) / (f + _K1 * (1 - _B + _B * len(d) / media))
        if puntos > 0:
            puntuadas.append((round(puntos, 4), unidad, sum(1 for f in frecuencias.values() if f)))
    puntuadas.sort(key=lambda x: (-x[0], x[1][0], x[1][1] or ""))
    incluir = set(incluir) | {"vigente"}
    indicios = no_declaradas(snapshot)
    candidatos, excluidos = [], {c: 0 for c in CLASES if c != "vigente"}
    total, por_registro = 0, {}
    for puntos, (ident, ancla, _, visible), coinciden in puntuadas:
        clase, estado, vigencia, rige_ahora = _clase(consulta, snapshot, ident, ancla)
        if clase not in incluir:
            excluidos[clase] += 1
            continue
        if ident in por_registro:  # un candidato por registro: las demás cláusulas que coinciden, en `otras_anclas`
            por_registro[ident].setdefault("otras_anclas", []).append(ancla)
            continue
        total += 1
        if len(candidatos) >= limite:
            por_registro[ident] = {}
            continue
        r = snapshot.registros[ident]
        c = {
            "id": ident,
            "ancla": ancla,
            "referencia": f"{ident}#{ancla}" if ancla else ident,
            "tipo": r.get("type"),
            "titulo": r.get("title"),
            "clase": clase,
            "estado": estado,
            "vigencia": vigencia,
            "puntuacion": puntos,
            "terminos_coincidentes": coinciden,
            "fragmento": _fragmento(visible, q),
            "ruta": snapshot.rutas.get(ident),
        }
        if rige_ahora:
            c["rige_ahora"] = rige_ahora
        avisos = avisos_para(indicios, [ident])
        if avisos:
            c["avisos"] = avisos
        candidatos.append(c)
        por_registro[ident] = c
    advertencias = list(consulta.advertencias)
    if not q:
        advertencias.append("la consulta no tiene términos buscables (solo palabras vacías o signos)")
    elif not puntuadas:
        advertencias.append("sin coincidencias léxicas: no significa que la base no trate el tema")
    for clase, cuantos in excluidos.items():
        if cuantos:
            nombre = "propuestas" if clase == "propuesta" else "no vigentes"
            opcion = "propuestas" if clase == "propuesta" else "no_vigentes"
            advertencias.append(f"{cuantos} coincidencias en {nombre} no mostradas: añade --incluir {opcion}")
    if total > len(candidatos):
        advertencias.append(f"se muestran {len(candidatos)} de {total} candidatos: sube --limite para ver más")
    if candidatos:
        advertencias.append(
            "la búsqueda encuentra candidatos, no decide qué rige: confírmalo con consultar o consolidar"
        )
    return {
        "consulta": texto,
        "terminos": q,
        "candidatos": candidatos,
        "excluidos": excluidos,
        "examinados": n,
        "truncado": total > len(candidatos),
        "advertencias": advertencias,
    }
