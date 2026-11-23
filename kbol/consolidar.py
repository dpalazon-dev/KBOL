"""Consolidado de cláusulas para dos cortes temporales (núcleo 0.7, «Modificación por cláusulas» y «Dos tiempos»).

Solo lee el snapshot. Una modificación rige cuando su decisión está aceptada en el corte de conocimiento y su validez
cubre `valido_en`. Cada cláusula aplicable viaja con su origen y su cadena de sustituciones; las propuestas se
devuelven aparte como no vinculantes. Dos modificaciones vigentes de la misma cláusula sin sucesión declarada son un
conflicto y no se ordenan por fecha. Retirar una modificadora no resucita el texto anterior.

La sucesión entre dos modificaciones de la misma cláusula se declara con `depende_de` hacia la anterior. Una sucesión
mutua, o un ciclo de `deja_obsoleta`, no decide nada: el resultado es un conflicto o una vigencia ambigua.
"""

from .eventos import ErrorDeHistorial, admitidos, historial_de_estado, rige_en
from .markdown import ErrorDeMarca, clausulas
from .sustituciones import avisos_para, no_declaradas
from .tiempo import comparable, instante

RIGE, FUTURA, RETIRADA, NO_CONSTABA, NO_EFECTIVA, AMBIGUA, SIN_HISTORIAL = (
    "rige",
    "futura",
    "retirada",
    "no_constaba",
    "no_efectiva",
    "ambigua",
    "sin_historial",
)


class _Consulta:
    def __init__(self, snapshot, valido_en, conocido_hasta):
        self.snap = snapshot
        self.valido_en = valido_en
        self.conocido_hasta = conocido_hasta
        self.regs = {k: r for k, r in snapshot.registros.items() if r.get("type") == "decision"}
        self.advertencias = []
        self.propuestas, self.futuras, self.conflictos = [], [], []
        self._situacion, self._anclas, self._estado = {}, {}, {}
        self.por_destino = {}
        for ident, r in self.regs.items():
            for mod in r.get("modifica") or []:
                if isinstance(mod, dict) and isinstance(mod.get("destino"), str):
                    self.por_destino.setdefault(mod["destino"], []).append((ident, mod))
        self._en_ciclo = self._ciclos_de_sucesion()

    def _ciclos_de_sucesion(self):
        """Decisiones en un ciclo de `deja_obsoleta` (prohibido, VAL-07): su vigencia no se decide."""
        sucede = {i: [d for d in r.get("deja_obsoleta") or [] if d in self.regs] for i, r in self.regs.items()}
        en_ciclo, color = set(), {}

        def visitar(nodo, camino):
            color[nodo] = 1
            for sig in sucede[nodo]:
                if color.get(sig) == 1:
                    en_ciclo.update(camino[camino.index(sig) :])
                elif color.get(sig) is None:
                    visitar(sig, camino + [sig])
            color[nodo] = 2

        for nodo in sorted(sucede):
            if nodo not in color:
                visitar(nodo, [nodo])
        return en_ciclo

    def avisar(self, texto):
        if texto not in self.advertencias:
            self.advertencias.append(texto)

    def anclas(self, ident):
        if ident not in self._anclas:
            cuerpo = self.snap.cuerpos.get(ident)
            try:
                self._anclas[ident] = clausulas(cuerpo) if cuerpo is not None else None
            except ErrorDeMarca as exc:
                self.avisar(f"{ident}: cuerpo mal formado ({exc})")
                self._anclas[ident] = None
        return self._anclas[ident]

    def situacion(self, ident):
        """Situación de una decisión en los cortes, calculada una vez por consulta y con independencia del orden."""
        if ident not in self._situacion:
            if ident in self._en_ciclo:
                self.avisar(f"CONFLICTO_NORMATIVO: {ident} está en un ciclo de deja_obsoleta; su vigencia no se decide")
                self._situacion[ident] = AMBIGUA
            else:
                self._situacion[ident] = self._calcular(ident)
        return self._situacion[ident]

    def _calcular(self, ident):
        r = self.regs[ident]
        if not admitidos(r.get("eventos") or []):
            self.avisar(f"{ident}: sin historial admitido; no se considera")
            return SIN_HISTORIAL
        try:
            cadena = historial_de_estado(r["eventos"], self.conocido_hasta, "decision")
        except ErrorDeHistorial as exc:
            self.avisar(f"{exc.codigo}: {ident}: historial incoherente ({exc})")
            return AMBIGUA
        if not cadena:
            return NO_CONSTABA
        registrado, ultimo = cadena[-1]
        self._estado[ident] = ultimo["estado_nuevo"]
        if ultimo["estado_nuevo"] != "aceptada":
            return NO_EFECTIVA
        desde, hasta = ultimo.get("valido_desde"), ultimo.get("valido_hasta")
        sucedida = self._sucedida(ident)
        if sucedida is None:
            return AMBIGUA
        if sucedida:
            return RETIRADA
        try:
            vigente = rige_en(desde, hasta, self.valido_en)
        except ErrorDeHistorial as exc:
            self.avisar(f"{exc.codigo}: {ident}: {exc}")
            return AMBIGUA
        if vigente:
            if comparable(desde) < registrado:
                self.avisar(f"{ident}: incorporada el {ultimo['registrado_en']} con efecto retroactivo desde {desde}")
            return RIGE
        if hasta is not None and instante(hasta) <= instante(self.valido_en):
            return RETIRADA
        self._anotar(self.futuras, {"decision": ident, "valido_desde": desde})
        return FUTURA

    def _sucedida(self, ident):
        """True si una sucesora completa (`deja_obsoleta`) ya entró en vigor; None si no se puede decidir.

        Basta con que haya entrado en vigor: que después la sustituyan, la deroguen o venza no resucita la decisión
        que dejó obsoleta. Restablecer lo anterior exige una decisión nueva que lo diga.
        """
        ambigua = False
        for otro, r in self.regs.items():
            if otro == ident or ident not in (r.get("deja_obsoleta") or []):
                continue
            entro = self._entro_en_vigor(otro)
            if entro:
                return True
            ambigua = ambigua or entro is None
        return None if ambigua else False

    def _entro_en_vigor(self, ident):
        """True si la decisión está aceptada al corte y su validez empezó en o antes de `valido_en`; None si ambiguo."""
        r = self.regs[ident]
        try:
            cadena = historial_de_estado(r.get("eventos") or [], self.conocido_hasta, "decision")
        except ErrorDeHistorial:
            return None
        if not cadena or cadena[-1][1]["estado_nuevo"] != "aceptada":
            return False
        try:
            return rige_en(cadena[-1][1].get("valido_desde"), None, self.valido_en)
        except ErrorDeHistorial as exc:
            self.avisar(f"{exc.codigo}: sucesora {ident}: {exc}")
            return None

    def es_propuesta(self, ident):
        """Propuesta según el historial al corte, no según la cabecera actual."""
        self.situacion(ident)
        return self._estado.get(ident) == "propuesta"

    @staticmethod
    def _anotar(lista, elemento):
        if elemento not in lista:
            lista.append(elemento)

    def anotar_propuesta(self, ident, mod):
        self._anotar(
            self.propuestas, {"decision": ident, "modificacion": mod, "estado": "propuesta", "vinculante": False}
        )

    def _sucede_a(self, x, y):
        """x declara sucesión respecto de y con una dependencia hacia y."""
        deps = [d.get("destino", "") for d in self.regs[x].get("depende_de") or [] if isinstance(d, dict)]
        return any(d.split("#", 1)[0] == y for d in deps)

    def _ratificaciones(self, r):
        vigentes = []
        for ev in admitidos(r.get("eventos") or []):
            if self.conocido_hasta is not None and instante(ev["registrado_en"]) > instante(self.conocido_hasta):
                break
            if ev.get("tipo_evento") == "ratificacion":
                vigentes.append(ev["aprobacion"]["aprobacion_id"])
            elif ev.get("tipo_evento") == "revocacion_aprobacion" and ev.get("aprobacion_id") in vigentes:
                vigentes.remove(ev["aprobacion_id"])
        return vigentes

    def _heredada(self, r):
        """Autoridad heredada del formato anterior, si el registro entró por importación; None si no."""
        for ev in admitidos(r.get("eventos") or []):
            if ev.get("tipo_evento") == "importacion":
                return ev.get("autoridad_heredada")
        return None

    def _declaradas(self, r):
        """Ratificaciones vigentes por el canal declarado: aprobaciones citadas, sin autenticar."""
        vigentes = set(self._ratificaciones(r))
        return sorted(
            ev["aprobacion"]["aprobacion_id"]
            for ev in admitidos(r.get("eventos") or [])
            if ev.get("tipo_evento") == "ratificacion"
            and ev["aprobacion"]["aprobacion_id"] in vigentes
            and isinstance(ev["aprobacion"].get("comprobante"), dict)
            and ev["aprobacion"]["comprobante"].get("autenticada") is False
        )

    def _aprobaciones(self, r):
        """Las ratificaciones vigentes con quién, cuándo, por qué canal y con qué palabras, tal como las conserva el
        registro; sin comprobar. Lo que el comprobante no trae queda en None, no se deduce."""
        vigentes = set(self._ratificaciones(r))
        salida = []
        for ev in admitidos(r.get("eventos") or []):
            aprobacion = ev.get("aprobacion") if ev.get("tipo_evento") == "ratificacion" else None
            if not aprobacion or aprobacion["aprobacion_id"] not in vigentes:
                continue
            comprobante = aprobacion.get("comprobante")
            detalle = comprobante if isinstance(comprobante, dict) else {}
            salida.append(
                {
                    "aprobacion_id": aprobacion["aprobacion_id"],
                    "actor": aprobacion.get("actor"),
                    "roles": list(aprobacion.get("roles") or []),
                    "aprobada_en": aprobacion.get("aprobada_en"),
                    "mecanismo": detalle.get("mecanismo") or (ev.get("evidencia_evento") or {}).get("mecanismo"),
                    "cita": detalle.get("cita"),
                    "autenticada": detalle.get("autenticada"),
                }
            )
        return salida

    def resolver(self, ref, cadena=None):
        """Estado consolidado de una cláusula `ID#ancla`, siguiendo sustituciones y derogaciones."""
        cadena = (cadena or []) + [ref]
        ident, _, ancla = ref.partition("#")
        base = {"referencia": cadena[0], "cadena": cadena}
        if len(cadena) != len(set(cadena)):
            self.avisar(f"CONFLICTO_NORMATIVO: ciclo de sustituciones en {' → '.join(cadena)}")
            return {**base, "estado": "conflicto"}
        candidatas, retiradas = [], []
        for m, mod in self.por_destino.get(ref, []):
            if mod.get("tipo") not in ("sustitucion", "derogacion"):
                continue
            sit = self.situacion(m)
            if sit == RIGE:
                candidatas.append((m, mod))
            elif sit == RETIRADA:
                retiradas.append(m)
            elif sit == AMBIGUA:
                return {**base, "estado": "ambigua"}
            elif sit == NO_EFECTIVA and self.es_propuesta(m):
                self.anotar_propuesta(m, mod)
        finales = [(m, mod) for m, mod in candidatas if not any(o != m and self._sucede_a(o, m) for o, _ in candidatas)]
        if len(finales) > 1 or (candidatas and not finales):
            conflicto = {
                "codigo": "CONFLICTO_NORMATIVO",
                "clausula": ref,
                "candidatas": sorted(mod.get("por") or m for m, mod in candidatas),
            }
            self._anotar(self.conflictos, conflicto)
            return {**base, "estado": "conflicto"}
        if finales:
            m, mod = finales[0]
            if mod["tipo"] == "derogacion":
                return {**base, "estado": "derogada", "origen": m}
            return self.resolver(mod["por"], cadena)
        if retiradas:
            self.avisar(
                f"{ref}: la modificadora {', '.join(sorted(retiradas))} ya no rige y el texto anterior no se "
                "reactiva solo; hace falta una decisión que diga qué rige"
            )
            return {**base, "estado": "sin_regla"}
        anclas = self.anclas(ident)
        if anclas is None or ancla not in anclas:
            self.avisar(f"{ref}: texto no disponible en la revisión {self.snap.revision}")
            return {**base, "estado": "sin_texto", "origen": ref}
        r = self.regs[ident]
        autoridad = {
            "decision": ident,
            "autorizado_por": list(r.get("autorizado_por") or []),
            "ratificaciones": self._ratificaciones(r),
            "declaradas": self._declaradas(r),
            "heredada": self._heredada(r),
            "comprobada": False,
        }
        return {**base, "estado": "vigente", "texto": anclas[ancla], "origen": ref, "autoridad": autoridad}

    def adiciones(self, ident):
        entradas = []
        for m, mod in self.por_destino.get(ident, []):
            if mod.get("tipo") != "adicion":
                continue
            sit = self.situacion(m)
            extra = {"adicion_a": ident, "posicion": mod.get("posicion")}
            if sit == RIGE:
                entradas.append({**self.resolver(mod["por"]), **extra})
            elif sit == AMBIGUA:
                entradas.append(
                    {"referencia": mod.get("por"), "cadena": [mod.get("por")], "estado": "ambigua", **extra}
                )
            elif sit == NO_EFECTIVA and self.es_propuesta(m):
                self.anotar_propuesta(m, mod)
        return entradas


def vigencia_de(consulta, ident):
    """(vigencia, entradas) de una decisión: `total`, `parcial`, `no_vigente` o `no_constaba`, con sus cláusulas.

    Única definición de la vigencia de una decisión; la comparten la consolidación, las dependencias y el soporte.
    """
    sit = consulta.situacion(ident)
    if sit != RIGE:
        return ("no_constaba" if sit == NO_CONSTABA else "no_vigente"), []
    propias = [consulta.resolver(f"{ident}#{a}") for a in consulta.anclas(ident) or {}]
    entradas = propias + consulta.adiciones(ident)
    if not any(e["estado"] == "vigente" for e in entradas):
        return "no_vigente", entradas
    if any(e["estado"] != "vigente" or e.get("origen") != e["referencia"] for e in propias):
        return "parcial", entradas
    return "total", entradas


def consolidar(snapshot, ids, *, valido_en, conocido_hasta):
    """Cláusulas que rigen de las decisiones `ids` en `valido_en` con lo conocido hasta `conocido_hasta`.

    `conocido_hasta=None` usa todo el historial admitido del snapshot; el resultado lo declara en sus cortes y en
    sus advertencias.
    """
    q = _Consulta(snapshot, valido_en, conocido_hasta)
    resultado = {
        "cortes": {"valido_en": valido_en, "conocido_hasta": conocido_hasta, "revision": snapshot.revision},
        "clausulas": [],
        "vigencia": {},
        "propuestas": q.propuestas,
        "futuras": q.futuras,
        "conflictos": q.conflictos,
        "ausentes": [],
        "heredados": [],
        "advertencias": q.advertencias,
    }
    if conocido_hasta is None:
        q.avisar("sin corte de conocimiento: se usa todo el historial admitido de la revisión")
    vistas = {}
    for ref in ids:
        ident, _, ancla = ref.partition("#")
        if ident not in q.regs and ident in snapshot.heredados:
            ficha = snapshot.heredados[ident]
            resultado["heredados"].append(ficha)
            q.avisar(f"{ident}: formato heredado ({ficha['estado_heredado']}); sin historial admitido, no rige")
            continue
        if ident not in q.regs or (ancla and ancla not in (q.anclas(ident) or {})):
            resultado["ausentes"].append(ref)
            continue
        resultado["vigencia"][ident], entradas = vigencia_de(q, ident)
        if ancla:  # con ancla, solo esa cláusula; la vigencia sigue siendo la de la decisión
            entradas = [e for e in entradas if e["referencia"] == ref]
        for e in entradas:
            clave = e.get("origen") if e["estado"] == "vigente" else None
            if clave and clave in vistas:
                vistas[clave].setdefault("tambien_por", []).append(e["referencia"])
                continue
            if clave:
                vistas[clave] = e
            resultado["clausulas"].append(e)
    for aviso in avisos_para(no_declaradas(snapshot), [r.partition("#")[0] for r in ids]):
        q.avisar(aviso)
    return resultado
