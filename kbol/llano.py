"""Respuesta en lenguaje llano para `consultar`, `consolidar` y `buscar` (`--llano`).

Dice, en prosa breve, la regla, quién la aprobó y cuándo, y si rige en la fecha de la consulta. Los IDs y las anclas
solo aparecen con `--con-ids`; sin ellos, cada registro se nombra por su título. Lo aprobado y lo propuesto, heredado
o encontrado por búsqueda se distinguen por la etiqueta entre corchetes con que empieza cada bloque, y lo que no
consta se dice («no consta ninguna aprobación»), no se deduce.

Se construye desde el sobre de la orden y el snapshot que la respondió; no consulta nada más. Los avisos que no se
traducen se cuentan al final, con la indicación de pedir la salida JSON para verlos.
"""

from .consolidar import _Consulta, consolidar
from .sustituciones import no_declaradas

_MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
_TEXTO_MAX = 600
_REGLAS_MAX = 4


def _fecha(valor):
    if not valor:
        return "fecha desconocida"
    texto = str(valor)
    try:
        a, m, d = int(texto[:4]), int(texto[5:7]), int(texto[8:10])
    except ValueError:
        return texto
    return f"{d} {_MESES[m - 1]} {a}"


def _corto(texto):
    plano = " ".join(str(texto or "").split())
    return plano if len(plano) <= _TEXTO_MAX else plano[:_TEXTO_MAX].rsplit(" ", 1)[0] + "…"


class _Presentador:
    def __init__(self, snapshot, con_ids):
        self.snap, self.con_ids = snapshot, con_ids

    def nombre(self, ref):
        """«Título» del registro de `ref` y, si se piden, su ID y ancla."""
        ident = str(ref).partition("#")[0]
        r = self.snap.registros.get(ident) or {}
        titulo = r.get("title") or (self.snap.heredados.get(ident) or {}).get("title")
        if not titulo:
            return ref if self.con_ids else "un registro sin título"
        return f"«{titulo}» ({ref})" if self.con_ids else f"«{titulo}»"

    def persona(self, actor):
        if not actor:
            return "alguien que no consta"
        ident = str(actor).split(":", 1)[-1]
        r = self.snap.registros.get(ident)
        if r and r.get("title"):
            return f"{r['title']} ({ident})" if self.con_ids else r["title"]
        return str(actor) if self.con_ids else "una persona sin ficha en la base"

    def aprobacion(self, autoridad):
        aprobaciones = (autoridad or {}).get("aprobaciones") or []
        if not aprobaciones:
            heredada = (autoridad or {}).get("heredada")
            if heredada and heredada.get("texto"):
                return f"Aprobación heredada del formato anterior: «{heredada['texto']}», sin comprobar."
            return "No consta ninguna aprobación."
        frases = []
        for a in aprobaciones:
            frase = f"Aprobación de {self.persona(a.get('actor'))}, el {_fecha(a.get('aprobada_en'))}"
            if a.get("cita"):
                frase += f", con estas palabras: «{_corto(a['cita'])}»"
            if a.get("autenticada") is False:
                frase += " (aprobación declarada, sin autenticar)"
            frases.append(frase + ".")
        return " ".join(frases)

    def etiqueta(self, tipo, estado):
        if tipo == "decision":
            return {
                "aceptada": "[APROBADA]",
                "propuesta": "[PROPUESTA: no aprobada, no rige]",
                "rechazada": "[RECHAZADA: no rige]",
            }.get(estado, f"[{str(estado or 'sin estado').upper()}]")
        if estado in ("propuesta", "propuesto", "borrador"):
            return f"[{tipo.upper()} PROPUESTO: sin aceptar]"
        return f"[{str(tipo or 'registro').upper()}, {estado or 'sin estado'}]"

    def sustituciones(self, ident):
        frases = []
        for i in no_declaradas(self.snap):
            if i["destino"] == ident:
                frases.append(
                    f"Ojo: {self.nombre(i['registro'])} dice sustituirla o derogarla, al menos en parte, sin "
                    "declararlo; puede que no rija tal como aparece aquí."
                )
            elif i["registro"] == ident:
                frases.append(
                    f"Ojo: dice sustituir o derogar a {self.nombre(i['destino'])} sin declararlo; lo que diga "
                    "aquella puede seguir saliendo como vigente."
                )
        return frases

    def reglas(self, ident, cortes):
        """Líneas con lo que rige de una decisión y lo que la sustituye."""
        res = consolidar(self.snap, [ident], **cortes)
        lineas = []
        for c in res["clausulas"][:_REGLAS_MAX]:
            if c["estado"] != "vigente":
                lineas.append(f"Una parte ya no rige ({c['estado'].replace('_', ' ')}).")
                continue
            ancla = f" [{c['origen']}]" if self.con_ids else ""
            if c.get("origen") != c["referencia"]:
                lineas.append(f"Sustituida por {self.nombre(c['origen'])}: {_corto(c.get('texto'))}{ancla}")
            else:
                lineas.append(f"Dice: {_corto(c.get('texto'))}{ancla}")
        if len(res["clausulas"]) > _REGLAS_MAX:
            lineas.append(f"Y {len(res['clausulas']) - _REGLAS_MAX} cláusulas más (pide la salida JSON).")
        return lineas

    def vigencia(self, vigencia, fecha, inversas):
        if vigencia == "total":
            return f"Rige entera a {fecha}."
        if vigencia == "parcial":
            return f"Rige solo en parte a {fecha}."
        motivo = ""
        if inversas and inversas.get("dejada_obsoleta_por"):
            motivo = ": la dejó obsoleta " + ", ".join(self.nombre(i) for i in inversas["dejada_obsoleta_por"])
        elif inversas and inversas.get("modificada_por"):
            motivo = ": la modificó " + ", ".join(self.nombre(i) for i in inversas["modificada_por"])
        return f"No rige a {fecha}{motivo}."


def _consultar(p, salida, cortes, fecha):
    bloques = []
    for res in salida["resultado"].get("resultados", []):
        ref = res["referencia"]
        if res["encontrado"] == "ausente":
            bloques.append([f"[NO ENCONTRADO] No hay nada integrado en la base con {ref}. Un borrador que no ha pasado por la integración no cuenta: `kbol validar --modo canonico` dice por qué."])
            continue
        if res["encontrado"] == "heredado":
            bloques.append([f"[HEREDADO: no rige] {p.nombre(ref)} está en el formato antiguo y no se aplica."])
            continue
        if res["encontrado"] == "ancla_ausente":
            bloques.append([f"[NO ENCONTRADO] {p.nombre(res['id'])} no tiene la cláusula que se pide."])
            continue
        tipo, estado = res.get("tipo"), res.get("estado")
        lineas = [f"{p.etiqueta(tipo, estado)} {p.nombre(ref)}"]
        if tipo == "decision":
            if res.get("clausula"):
                c = res["clausula"]
                if c.get("estado") == "vigente" and c.get("origen") == ref:
                    lineas.append(f"Rige a {fecha}. Dice: {_corto(c.get('texto'))}")
                elif c.get("estado") == "vigente":
                    lineas.append(f"Esta cláusula ya no rige a {fecha}; la sustituyó {p.nombre(c['origen'])}.")
                    lineas.append(f"Ahora dice: {_corto(c.get('texto'))}")
                else:
                    lineas.append(f"Esta cláusula no rige a {fecha} ({str(c.get('estado')).replace('_', ' ')}).")
            else:
                lineas.append(p.vigencia(res.get("vigencia"), fecha, res.get("relaciones_inversas")))
                if res.get("vigencia") in ("total", "parcial"):
                    lineas += p.reglas(res["id"], cortes)
        else:
            r = p.snap.registros.get(res["id"]) or {}
            if r.get("afirmacion"):
                lineas.append(f"Afirma: {_corto(r['afirmacion'])}")
            elif res.get("texto"):
                lineas.append(f"Dice: {_corto(res['texto'])}")
            elif r.get("description") and r["description"] != r.get("title"):
                lineas.append(_corto(r["description"]))
        lineas.append(p.aprobacion(res.get("autoridad")))
        evidencia = res.get("evidencia")
        if evidencia and not evidencia.get("suficiente"):
            lineas.append("Su evidencia no basta: alguna de sus fuentes falta o no rige.")
        lineas += p.sustituciones(res["id"])
        bloques.append(lineas)
    return bloques


def _consolidar(p, salida, cortes, fecha):
    resultado = salida["resultado"]
    bloques = []
    for ident, vigencia in resultado.get("vigencia", {}).items():
        r = p.snap.registros.get(ident) or {}
        lineas = [f"{p.etiqueta('decision', r.get('estado'))} {p.nombre(ident)}", p.vigencia(vigencia, fecha, None)]
        lineas += p.reglas(ident, cortes)
        lineas += p.sustituciones(ident)
        bloques.append(lineas)
    for prop in resultado.get("propuestas", []):
        bloques.append([f"[PROPUESTA: no aprobada, no rige] {p.nombre(prop['decision'])} propone cambiarla."])
    for ref in resultado.get("ausentes", []):
        bloques.append([f"[NO ENCONTRADO] No hay nada integrado en la base con {ref}. Un borrador que no ha pasado por la integración no cuenta: `kbol validar --modo canonico` dice por qué."])
    return bloques


def _buscar(p, salida, cortes, fecha):
    resultado = salida["resultado"]
    bloques = []
    for c in resultado.get("candidatos", []):
        etiqueta = p.etiqueta(c["tipo"], c["estado"])
        lineas = [f"[CANDIDATO por búsqueda, sin confirmar] {etiqueta} {p.nombre(c['referencia'])}"]
        if c["clase"] == "vigente":
            lineas.append(f"Rige a {fecha}.")
        elif c.get("rige_ahora"):
            lineas.append(f"Ya no rige; ahora rige {p.nombre(c['rige_ahora'])}.")
        else:
            lineas.append(f"No rige a {fecha}.")
        lineas.append(f"Fragmento: {c['fragmento']}")
        r = p.snap.registros.get(c["id"]) or {}
        if r.get("type") == "decision":
            lineas.append(p.aprobacion({"aprobaciones": _Consulta(p.snap, **cortes)._aprobaciones(r)}))
        lineas += p.sustituciones(c["id"])
        bloques.append(lineas)
    if not bloques:
        bloques.append(["No hay coincidencias entre lo vigente."])
    excluidos = resultado.get("excluidos", {})
    if any(excluidos.values()):
        partes = []
        if excluidos.get("propuesta"):
            partes.append(f"{excluidos['propuesta']} en propuestas (--incluir propuestas)")
        if excluidos.get("no_vigente"):
            partes.append(f"{excluidos['no_vigente']} en lo que ya no rige (--incluir no_vigentes)")
        bloques.append(["Hay más coincidencias que no se muestran: " + "; ".join(partes) + "."])
    return bloques


def presentar(op, salida, snapshot, *, con_ids=False):
    """Texto llano del sobre `salida` de `op`."""
    p = _Presentador(snapshot, con_ids)
    cortes = {"valido_en": salida["valido_en"], "conocido_hasta": salida["conocido_hasta"]}
    fecha = _fecha(cortes["valido_en"])
    cabecera = f"A fecha {fecha}"
    if cortes["conocido_hasta"]:
        cabecera += f", con lo conocido hasta {_fecha(cortes['conocido_hasta'])}"
    if op == "buscar":
        cabecera += f". Búsqueda por texto: «{salida['resultado']['consulta']}»"
    bloques = {"consultar": _consultar, "consolidar": _consolidar, "buscar": _buscar}[op](p, salida, cortes, fecha)
    texto = [cabecera + "."]
    for b in bloques:
        texto.append("\n".join([b[0], *(f"  {x}" for x in b[1:])]))
    resto = [a for a in salida.get("advertencias", []) if "SUSTITUCION_NO_DECLARADA" not in a]
    if salida["resultado"].get("estado") == "parcial":
        texto.append("La respuesta es parcial: falta algo de lo que se pidió o no se pudo leer toda la base.")
    if salida["cobertura"].get("truncado") and op == "buscar" and salida["resultado"].get("candidatos"):
        texto.append("Se muestran solo los primeros candidatos (--limite para ver más).")
    if resto:
        cuantos = "Hay 1 aviso técnico más" if len(resto) == 1 else f"Hay {len(resto)} avisos técnicos más"
        texto.append(f"{cuantos}: pide la salida sin --llano para verlos.")
    return "\n\n".join(texto)
