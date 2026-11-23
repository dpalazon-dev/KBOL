"""CLI `kbol`: todas las operaciones devuelven el sobre contractual; las no habilitadas fallan cerradas.

Códigos de salida: 0 completado, 1 fallido, 2 bloqueado, 3 parcial (la consulta excluyó registros que podían
cambiar el resultado, o no examinó ninguno).
"""

import argparse
import json
import re
import subprocess
import sys
import uuid
from pathlib import Path

from . import __version__, llano
from . import proponer as proponer_mod
from . import relevo as relevo_mod
from . import sesion as sesion_mod
from . import verificar as verificar_mod
from .arranque import arrancar
from .buscar import buscar
from .citas import comprobar as comprobar_citas
from .consolidar import consolidar
from .consultar import consultar
from .contexto import preparar_contexto, presentar
from .core import ErrorDeFormato, parse
from .declarada import MECANISMO as MECANISMO_DECLARADA
from .declarada import VerificadorDeclarado
from .dependencias import listos
from .digest import digest
from .enlaces import comprobar as comprobar_enlaces
from .enlaces import configuracion as configuracion_enlaces
from .exportar import exportar as exportar_skills
from .huellas import commits_fuera_del_flujo
from .huellas import desvios as desvios_mod
from .impacto import impacto
from .integrar import ACTOR as ACTOR_INTEGRADOR
from .integrar import MODOS, integrar
from .integridad import comprobar as comprobar_integridad
from .migracion import formato_de, inspeccionar_carpeta
from .paquete import preparar_aprobacion
from .paquete import presentar as presentar_aprobacion
from .schema import validar
from .snapshot import cargar, entorno_git
from .soporte import delta, soporte
from .tiempo import es_instante
from .vocabulario import revisar, vigente

HABILITADAS = (
    "validar",
    "migrar",
    "digest",
    "consolidar",
    "listos",
    "impacto",
    "relevo",
    "preparar_contexto",
    "verificar",
    "consultar",
    "buscar",
    "integrar",
    "arranque",
    "desvios",
    "citas",
    "enlaces",
    "integridad",
    "soporte",
    "preparar_aprobacion",
    "vocabulario",
    "sesion",
    "proponer",
    "exportar_skills",
)
NO_HABILITADAS = ("ingerir",)
NO_EVALUADO = ["autoridad", "vigencia", "referencias entre registros", "admision de eventos"]


def sobre(operacion, resultado, revision=None, advertencias=None, alcance=None, no_evaluado=None):
    return {
        "operacion": operacion,
        "operacion_id": str(uuid.uuid4()),
        "revision": revision,
        "valido_en": None,
        "conocido_hasta": None,
        "resultado": resultado,
        "advertencias": advertencias or [],
        "cobertura": {
            "alcance": alcance,
            "truncado": False,
            "no_evaluado": NO_EVALUADO if no_evaluado is None else no_evaluado,
        },
    }


def _bloqueado(op, motivo, codigo=None):
    return sobre(op, {"estado": "bloqueado", "codigo": codigo, "motivo": motivo}), 2


def _fallido(op, codigo, motivo, alcance):
    return sobre(op, {"estado": "fallido", "codigo": codigo, "motivo": motivo}, alcance=alcance), 1


def _por_examen(examinados, motivo, avisos, parcial=False):
    """(estado, salida, avisos) de una operación según lo examinado.

    Examinar cero elementos no es completar: termina `parcial` con el motivo entre los avisos. Que una
    comparación no encuentre cambios no es no haber examinado; eso lo decide quien llama al contar.
    """
    if examinados == 0:
        return "parcial", 3, [*avisos, motivo]
    return ("parcial", 3, avisos) if parcial else ("completado", 0, avisos)


def _cobertura_de_carga(cobertura):
    """Campos de la cobertura de una carga de registros que el sobre expone."""
    return {
        "registros_leidos": cobertura["leidos"],
        "omitidos": cobertura["omitidos"],
        "invalidos": cobertura["invalidos"],
        "heredados": cobertura["heredados"],
        "truncado": cobertura["estado"] != "completo",
    }


def ejecutar(args):
    op = args.operacion
    if op in NO_HABILITADAS:
        return _bloqueado(op, "capacidad no habilitada en esta versión")
    if not args.ruta:
        return _bloqueado(op, "falta la ruta")
    if op == "exportar_skills":
        return _exportar_skills(args)
    ruta = Path(args.ruta)
    if not ruta.exists():
        return _fallido(op, "REFERENCIA_AUSENTE", f"no existe: {args.ruta}", args.ruta)
    if op == "migrar":
        if not args.revision:
            return _bloqueado(op, "la migración en seco necesita --revision")
        formato, fallo = _formato(op, args)
        if fallo:
            return fallo
        res = inspeccionar_carpeta(ruta, args.revision, formato)
        estado, codigo, avisos = _por_examen(
            res["resumen"]["propuestos"], f"ningún registro heredado en {args.ruta}: ¿es la carpeta correcta?", []
        )
        return sobre(op, {"estado": estado, **res}, args.revision, avisos, alcance=args.ruta), codigo
    if op in ("consolidar", "listos", "consultar", "soporte", "vocabulario", "buscar"):
        return _consulta(op, args)
    if op == "impacto":
        return _impacto(args)
    if op == "enlaces":
        return _enlaces(args)
    if op == "integridad":
        return _integridad(args)
    if op == "relevo":
        return _relevo(args)
    if op == "preparar_contexto":
        return _preparar_contexto(args)
    if op == "verificar":
        return _verificar(args)
    if op == "integrar":
        return _integrar(args)
    if op == "arranque":
        return _arranque(args)
    if op == "desvios":
        return _desvios(args)
    if op == "citas":
        return _citas(args)
    if op == "preparar_aprobacion":
        return _preparar_aprobacion(args)
    if op == "sesion":
        return _sesion(args)
    if op == "proponer":
        return _proponer(args)
    try:
        registro, cuerpo = parse(ruta.read_text(encoding="utf-8"))
    except OSError as exc:  # una carpeta o un archivo ilegible no es un registro
        return _fallido(op, "REFERENCIA_AUSENTE", f"no se pudo leer {args.ruta}: {exc}", args.ruta)
    except (ErrorDeFormato, UnicodeDecodeError) as exc:
        return _fallido(op, "ESQUEMA_INVALIDO", str(exc), args.ruta)
    if op == "validar":
        hallazgos = validar(registro, cuerpo, modo=args.modo)
        errores = [h for h in hallazgos if h["severidad"] == "error"]
        avisos = [f"{h['ruta']}: {h['mensaje']}" for h in hallazgos if h["severidad"] != "error"]
        estado = "fallido" if errores else "completado"
        return sobre(op, {"estado": estado, "errores": errores}, args.revision, avisos, args.ruta), int(bool(errores))
    errores = [h for h in validar(registro, cuerpo) if h["severidad"] == "error"]
    if errores:
        return sobre(op, {"estado": "fallido", "codigo": "ESQUEMA_INVALIDO", "errores": errores}, alcance=args.ruta), 1
    try:
        efectos = _leer_json(args.efectos) if args.efectos else []
        valor = digest(registro, cuerpo, efectos)
    except (OSError, ValueError) as exc:
        return _fallido(op, "ESQUEMA_INVALIDO", str(exc), args.ruta)
    resultado = {"estado": "completado", "digest": valor}
    return sobre(op, resultado, args.revision, alcance=args.ruta, no_evaluado=["autoridad", "vigencia"]), 0


def _relevo(args):
    """Relevo de una tarea; con --guardar, antes guarda el relevo que da ese JSON (estado local, no conocimiento)."""
    if not args.tarea:
        return _bloqueado("relevo", "relevo necesita --tarea")
    try:
        if args.guardar:
            relevo_mod.guardar(
                args.ruta, args.tarea, _leer_json(args.guardar), rama_canonica=args.rama_canonica or "main"
            )
        res = relevo_mod.relevo(args.ruta, args.tarea, rama_canonica=args.rama_canonica or "main")
    except (OSError, ValueError) as exc:
        return _fallido("relevo", "ESQUEMA_INVALIDO", str(exc), args.ruta)
    no_evaluado = ["verificaciones no ejecutadas por el relevo", "lo que nunca se guardó"]
    return sobre(
        "relevo", {"estado": "completado", **res}, res["git"].get("cabeza"), alcance=args.ruta, no_evaluado=no_evaluado
    ), 0


def _verificar(args):
    """Ejecuta una verificación declarada en la instalación y la anota en el relevo de la tarea."""
    faltan = [
        n
        for n, v in (
            ("--tarea", args.tarea),
            ("--instalacion", args.instalacion),
            ("--verificacion", args.verificacion),
        )
        if not v
    ]
    if faltan:
        return _bloqueado("verificar", f"verificar necesita {', '.join(faltan)}")
    try:
        instalacion, procedencia = verificar_mod.instalacion_controlada(args.ruta, args.instalacion)
        res = verificar_mod.ejecutar(
            args.ruta,
            args.tarea,
            instalacion,
            args.verificacion,
            rama_canonica=args.rama_canonica or "main",
            procedencia=procedencia,
        )
    except (OSError, ValueError) as exc:
        return _fallido("verificar", "ESQUEMA_INVALIDO", str(exc), args.ruta)
    no_evaluado = [
        "aislamiento de la ejecución",
        "efectos fuera del árbol de trabajo",
        "archivos ignorados por git",
        "recibo de la ejecución",
    ]
    avisos = []
    if res["entorno_ref"]["externo"]:
        avisos.append(
            "el intérprete no es el del .venv de la raíz: lo instalado allí como editable puede ser de otra copia"
        )
    # El resultado de la verificación es el del sobre: fallida, fallido; sin saber, parcial.
    estado, codigo = {"superado": ("completado", 0), "fallido": ("fallido", 1)}.get(res["resultado"], ("parcial", 3))
    resultado = {"estado": estado, **res}
    if estado == "fallido":
        # `codigo` sigue siendo el código de salida de la orden verificada: el sobre no lo pisa.
        resultado["motivo"] = f"la verificación {args.verificacion} falló (código {res['codigo']})"
    elif estado == "parcial":
        avisos.append(
            f"la verificación {res['resultado']}: " + "; ".join(res["observaciones"] or ["sin observaciones"])
        )
    salida = sobre("verificar", resultado, res["revision_probada"], avisos, alcance=args.ruta, no_evaluado=no_evaluado)
    return salida, codigo


def _preparar_contexto(args):
    """Paquete de contexto de una tarea (solo lectura); --texto lo presenta para inyectarlo en una sesión."""
    faltan = [
        n
        for n, v in (
            ("--tarea", args.tarea),
            ("--ambito", args.ambito),
            ("--instalacion", args.instalacion),
            ("--valido-en", args.valido_en),
        )
        if not v
    ]
    if faltan:
        return _bloqueado("preparar_contexto", f"preparar_contexto necesita {', '.join(faltan)}")
    for nombre, valor in (("--valido-en", args.valido_en), ("--conocido-hasta", args.conocido_hasta)):
        if valor is not None and not es_instante(valor):
            return _bloqueado("preparar_contexto", f"{nombre} no es un instante ISO 8601 con zona", "TIEMPO_AMBIGUO")
    try:
        instalacion = _leer_json(args.instalacion)
        paquete = preparar_contexto(
            args.ruta,
            tarea=args.tarea,
            objetivo=args.objetivo,
            ambito=args.ambito,
            carpeta=_carpetas(args),
            instalacion=instalacion,
            valido_en=args.valido_en,
            conocido_hasta=args.conocido_hasta,
            revision=args.revision,
            presupuesto=args.presupuesto,
            heredados=args.heredados_carpeta,
        )
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        return _fallido("preparar_contexto", "REFERENCIA_AUSENTE", str(exc), args.ruta)
    if args.texto:
        return presentar(paquete), 0 if paquete["estado"] == "completado" else 3
    advertencias = paquete.pop("advertencias")
    cobertura = paquete.pop("cobertura")
    salida = sobre(
        "preparar_contexto",
        paquete,
        paquete["revision"],
        advertencias,
        f"{args.ruta}:{args.carpeta}",
        cobertura["no_evaluado"],
    )
    salida["cobertura"].update({k: cobertura[k] for k in ("estado", "leidos", "invalidos")})
    salida["valido_en"], salida["conocido_hasta"] = args.valido_en, args.conocido_hasta
    return salida, 0 if paquete["estado"] == "completado" else 3


def _impacto(args):
    """Consumidores afectados por el paso de --base a --revision (o al disco). Estructural: no lee ningún reloj.

    La base se carga como revisión canónica; la final, como árbol de una propuesta, cuyos registros nuevos aún no
    tienen eventos. Sin arista declarada no hay impacto calculado: lo que no se declara no se ve.
    """
    if not args.base:
        return _bloqueado("impacto", "impacto necesita --base: la revisión de partida")
    try:
        base, cob_b = cargar(args.ruta, _carpetas(args), args.base, heredados=True)
        final, cob_f = cargar(args.ruta, _carpetas(args), args.revision, modo="propuesta", heredados=True)
    except (OSError, UnicodeDecodeError, subprocess.CalledProcessError) as exc:
        return _fallido("impacto", "REFERENCIA_AUSENTE", f"no se pudo leer una revisión: {exc}", args.ruta)
    coberturas = (cob_b, cob_f)
    alcance = f"{args.ruta}:{args.carpeta}"
    no_evaluado = ["dependencias no declaradas", "autenticidad de las aprobaciones"]
    if any(c["estado"] == "bloqueado" for c in coberturas):
        errores = [h for c in coberturas for h in c["hallazgos"] if h["severidad"] == "error"]
        resultado = {
            "estado": "bloqueado",
            "codigo": errores[0]["codigo"] if errores else None,
            "motivo": "snapshot incoherente",
            "hallazgos": errores,
        }
        return sobre("impacto", resultado, final.revision, cob_f["advertencias"], alcance, no_evaluado), 2
    res = impacto(base, final)
    advertencias = cob_b["advertencias"] + cob_f["advertencias"] + res.pop("advertencias")
    parcial = any(c["estado"] == "parcial" for c in coberturas)
    # Sin cambios sigue siendo completado; parcial solo si la revisión final no cargó ningún registro.
    estado, codigo, advertencias = _por_examen(
        cob_f["leidos"],
        "la revisión final no cargó ningún registro: ¿están bien la carpeta y la revisión?",
        advertencias,
        parcial,
    )
    resultado = {"estado": estado, **res}
    if parcial:
        resultado["hallazgos"] = cob_b["hallazgos"] + cob_f["hallazgos"]
    salida = sobre("impacto", resultado, final.revision, advertencias, alcance, no_evaluado)
    salida["cobertura"].update(
        {
            "registros_leidos": cob_f["leidos"],
            "invalidos": cob_b["invalidos"] + cob_f["invalidos"],
            "truncado": estado == "parcial",
        }
    )
    return salida, codigo


def _consulta(op, args):
    """Consultas de solo lectura sobre un snapshot: el reloj y los cortes son entradas explícitas.

    `soporte` con `--antes-valido-en` o `--antes-conocido-hasta` compara dos pares de cortes; el que no se da es el
    mismo que el de después.
    """
    if not args.valido_en:
        return _bloqueado(op, "--valido-en es obligatorio: el reloj de la consulta es una entrada explícita")
    instantes = (
        ("--valido-en", args.valido_en),
        ("--conocido-hasta", args.conocido_hasta),
        ("--antes-valido-en", args.antes_valido_en),
        ("--antes-conocido-hasta", args.antes_conocido_hasta),
    )
    for nombre, valor in instantes:
        if valor is not None and not es_instante(valor):
            return _bloqueado(op, f"{nombre} no es un instante ISO 8601 con zona", "TIEMPO_AMBIGUO")
    comparar = args.antes_valido_en is not None or args.antes_conocido_hasta is not None
    if comparar and op != "soporte":
        return _bloqueado(op, "--antes-valido-en y --antes-conocido-hasta solo valen para soporte")
    if op in ("consolidar", "consultar") and not args.ids:
        return _bloqueado(op, f"{op} necesita --ids")
    if op == "buscar" and not (args.consulta or "").strip():
        return _bloqueado(op, "buscar necesita --consulta con el texto que se busca")
    if op == "buscar" and args.ids:
        return _bloqueado(op, "buscar no admite --ids: para un ID conocido, consultar")
    if op == "vocabulario" and args.ids:
        return _bloqueado(op, "vocabulario revisa toda la base: no admite --ids")
    carpeta = args.carpeta.split(",") if "," in args.carpeta else args.carpeta
    formato, fallo = _formato(op, args)
    if fallo:
        return fallo
    try:
        heredados = args.heredados or op in ("consultar", "soporte", "vocabulario", "buscar")
        snapshot, cobertura = cargar(args.ruta, carpeta, args.revision, heredados=heredados, formato=formato)
    except (OSError, UnicodeDecodeError, subprocess.CalledProcessError) as exc:
        return _fallido(op, "REFERENCIA_AUSENTE", f"no se pudo leer el snapshot: {exc}", args.ruta)
    cortes = {"valido_en": args.valido_en, "conocido_hasta": args.conocido_hasta}
    sin_evaluar = []
    if cobertura["estado"] == "bloqueado":
        errores = [h for h in cobertura["hallazgos"] if h["severidad"] == "error"]
        resultado, codigo, advertencias = (
            {
                "estado": "bloqueado",
                "codigo": errores[0]["codigo"],
                "motivo": "snapshot incoherente",
                "hallazgos": errores,
            },
            2,
            cobertura["advertencias"],
        )
    else:
        if op == "consultar":
            res = consultar(snapshot, args.ids, **cortes)
        elif op == "buscar":
            incluir = [_INCLUIR[x] for x in args.incluir]
            res = buscar(snapshot, args.consulta, **cortes, incluir=incluir, limite=args.limite)
        elif op == "soporte" and comparar:
            antes = {
                "valido_en": args.antes_valido_en or args.valido_en,
                "conocido_hasta": args.antes_conocido_hasta or args.conocido_hasta,
            }
            res = delta(snapshot, antes, cortes, args.ids or None)
        elif op == "soporte":
            res = soporte(snapshot, **cortes, ids=args.ids or None)
        elif op == "consolidar":
            res = consolidar(snapshot, args.ids, **cortes)
        elif op == "vocabulario":
            res = _vocabulario(snapshot, cortes)
            sin_evaluar = res.pop("no_evaluado")
        else:
            res = listos(snapshot, **cortes)
        advertencias = cobertura["advertencias"] + res.pop("advertencias")
        # Una decisión heredada pedida no se resuelve: se nombra, pero no rige (lectura compatible). Una consulta
        # por ID que no encuentra lo canónico tampoco está completa.
        no_canonicos = [x for x in res.get("resultados", []) if x["encontrado"] != "canonico"]
        ausentes = res.get("ausentes", [])
        parcial = cobertura["estado"] == "parcial" or bool(res.get("heredados")) or bool(no_canonicos) or bool(ausentes)
        advertencias += [f"{i}: no está en la base" for i in ausentes]
        if op == "listos":
            examinados, motivo = res["hitos_examinados"], "ningún hito examinado en la carpeta"
        elif op == "soporte":
            examinados, motivo = (
                res["registros_examinados"],
                "ningún registro examinado: ¿están bien la carpeta y los IDs?",
            )
        elif op == "vocabulario":
            examinados, motivo = res["registros_examinados"], "ningún registro examinado en la carpeta"
        elif op == "buscar":
            examinados, motivo = res["examinados"], "ningún registro examinado: ¿están bien la carpeta y la revisión?"
        else:
            examinados, motivo = cobertura["leidos"], "ningún registro leído: ¿están bien la carpeta y la revisión?"
        estado, codigo, advertencias = _por_examen(examinados, motivo, advertencias, parcial)
        resultado = {"estado": estado, **res}
        if estado == "parcial":
            resultado["hallazgos"] = cobertura["hallazgos"]
    no_evaluado = ["autenticidad de las aprobaciones", "integridad de las fuentes"]
    if op == "soporte":
        # Señala y no bloquea: un apoyo roto no cambia el código de salida.
        no_evaluado += ["respaldo semántico de los apoyos", "apoyos no declarados"]
    if op == "buscar":
        no_evaluado += ["similitud semántica: la búsqueda es léxica", "registros en formato heredado"]
    if op in ("consultar", "consolidar", "buscar"):
        no_evaluado += ["sustituciones no declaradas: solo indicios léxicos"]
    if op == "vocabulario":
        # Señala y no bloquea: un término no declarado no cambia el código de salida.
        no_evaluado += sin_evaluar
    salida = sobre(op, resultado, snapshot.revision, advertencias, f"{args.ruta}:{args.carpeta}", no_evaluado)
    salida["valido_en"], salida["conocido_hasta"] = args.valido_en, args.conocido_hasta
    salida["cobertura"].update(_cobertura_de_carga(cobertura))
    if op == "buscar" and resultado.get("truncado"):
        salida["cobertura"]["truncado"] = True
    if args.llano and resultado.get("estado") in ("completado", "parcial"):
        return llano.presentar(op, salida, snapshot, con_ids=args.con_ids), codigo
    return salida, codigo


_INCLUIR = {"propuestas": "propuesta", "no_vigentes": "no_vigente"}


def _vocabulario(snapshot, cortes):
    """Lo que rige del vocabulario del dominio en los cortes y sus usos en la base.

    Los registros heredados no se revisan: se nombran, y la consulta termina `parcial`.
    """
    voc = vigente(snapshot, **cortes)
    rev = revisar(snapshot, voc, conocido_hasta=cortes["conocido_hasta"])
    heredados = [snapshot.heredados[i] for i in sorted(snapshot.heredados)]
    avisos = [f"{f['id']}: formato heredado; su clase y su ámbito no se revisan" for f in heredados]
    return {
        "cortes": voc["cortes"],
        "declarado": voc["declarado"],
        "clases": voc["clases"],
        "alias": voc["alias"],
        "ambitos": voc["ambitos"],
        "no_declarados": rev["no_declarados"],
        "indeterminados": rev["indeterminados"],
        "retirados_en_uso": rev["retirados_en_uso"],
        "ambitos_sin_rol": rev["ambitos_sin_rol"],
        "registros_examinados": rev["registros_examinados"],
        "heredados": heredados,
        "no_evaluado": rev["cobertura"],
        "advertencias": voc["advertencias"] + rev["advertencias"] + avisos,
    }


_NOMBRE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,99}")
_NOMBRE_RAMA = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,199}")


def _formato(op, args):
    """(formato heredado que declara `--instalacion`, None); sin ella, el formato heredado por defecto. Si no vale, (None, salida)."""
    try:
        return formato_de(_leer_json(args.instalacion) if args.instalacion else {}), None
    except OSError as exc:
        return None, _fallido(op, "REFERENCIA_AUSENTE", f"no se pudo leer la instalación: {exc}", args.instalacion)
    except ValueError as exc:
        return None, _fallido(op, "ESQUEMA_INVALIDO", f"instalación mal formada: {exc}", args.instalacion)


def _carpetas(args):
    return args.carpeta.split(",") if "," in args.carpeta else args.carpeta


def _faltan(op, pares):
    faltan = [nombre for nombre, valor in pares if not valor]
    return _bloqueado(op, f"{op} necesita {', '.join(faltan)}") if faltan else None


def _git_cli(ruta, *args):
    p = subprocess.run(["git", "-C", str(ruta), *args], capture_output=True, text=True, env=entorno_git())
    return p.returncode, p.stdout.strip(), p.stderr.strip()


def _al_dia_con_el_remoto(op, ruta, remoto, rama, base):
    """Trae el remoto y exige que la base y la rama local sean su cabeza; None si lo están. Nunca sube nada."""
    if not _NOMBRE.fullmatch(remoto) or not _NOMBRE_RAMA.fullmatch(rama) or ".." in rama:
        return _bloqueado(op, "--remoto y --rama-canonica son nombres de git, sin opciones ni rutas")
    codigo, _, error = _git_cli(
        ruta, "fetch", "--quiet", "--end-of-options", remoto, f"refs/heads/{rama}:refs/remotes/{remoto}/{rama}"
    )
    if codigo != 0:
        return _fallido(op, "RESULTADO_DESCONOCIDO", f"no se pudo traer {remoto}/{rama}: {error}", ruta)
    _, cabeza, _ = _git_cli(ruta, "rev-parse", "--verify", f"refs/remotes/{remoto}/{rama}^{{commit}}")
    _, local, _ = _git_cli(ruta, "rev-parse", "--verify", f"refs/heads/{rama}^{{commit}}")
    if cabeza != base:
        motivo = f"{remoto}/{rama} está en {cabeza[:12]}, no en la base {base[:12]}: rehacer la propuesta sobre él"
        return _bloqueado(op, motivo, "BASE_CAMBIADA")
    if local != cabeza:
        return _bloqueado(op, f"la rama local {rama} no está al día con {remoto}: actualízala antes", "BASE_CAMBIADA")
    return None


def _integrar(args):
    """Integra con aprobaciones declaradas; con --remoto, comprueba antes que el remoto no ha avanzado.

    Con `--aprobacion decisiva`, las aprobaciones son opcionales: solo las necesita lo decisivo.
    """
    decisiva = args.aprobacion == "decisiva"
    error = _faltan(
        "integrar",
        (
            ("--rama-canonica", args.rama_canonica),
            ("--operacion-id", args.operacion_id),
            ("--base", args.base),
            ("--propuesta", args.propuesta),
            ("--aprobaciones", args.aprobaciones or decisiva),
            ("--actor", args.actor or not decisiva),
            ("--recibos", args.recibos),
        ),
    )
    if error:
        return error
    try:
        aprobaciones = _leer_json(args.aprobaciones) if args.aprobaciones else []
    except (OSError, ValueError) as exc:
        return _fallido("integrar", "ESQUEMA_INVALIDO", f"aprobaciones ilegibles: {exc}", args.aprobaciones)
    if (
        not isinstance(aprobaciones, list)
        or (not aprobaciones and not decisiva)
        or any(not isinstance(a, dict) or a.get("mecanismo") != MECANISMO_DECLARADA for a in aprobaciones)
    ):
        return _bloqueado("integrar", "la CLI integra con una lista de aprobaciones declaradas (kbol.declarada)")
    if args.remoto:
        error = _al_dia_con_el_remoto("integrar", args.ruta, args.remoto, args.rama_canonica, args.base)
        if error:
            return error
    recibo = integrar(
        args.ruta,
        rama=args.rama_canonica,
        carpeta=_carpetas(args),
        operacion_id=args.operacion_id,
        base_esperada=args.base,
        propuesta_rev=args.propuesta,
        revisiones=aprobaciones,
        verificador=VerificadorDeclarado(args.ruta),
        recibos=args.recibos,
        aprobacion=args.aprobacion or "toda",
        actor=args.actor or ACTOR_INTEGRADOR,
    )
    codigo = {"integrado": 0, "bloqueado": 2}.get(recibo.get("estado"), 1)
    return sobre("integrar", recibo, recibo.get("revision_integrada"), alcance=args.ruta), codigo


def _preparar_aprobacion(args):
    """Paquete de aprobación de una propuesta (solo lectura); --texto lo presenta a la persona.

    Bloqueado con el código de la puerta si la integración fuera a bloquear; parcial si no toca ningún registro.
    """
    op = "preparar_aprobacion"
    error = _faltan(
        op,
        (
            ("--operacion-id", args.operacion_id),
            ("--base", args.base),
            ("--propuesta", args.propuesta),
            ("--valido-en", args.valido_en),
        ),
    )
    if error:
        return error
    try:
        paquete = preparar_aprobacion(
            args.ruta,
            carpeta=_carpetas(args),
            operacion_id=args.operacion_id,
            base=args.base,
            propuesta=args.propuesta,
            valido_en=args.valido_en,
            conocido_hasta=args.conocido_hasta,
        )
    except (OSError, UnicodeDecodeError, subprocess.CalledProcessError) as exc:
        return _fallido(op, "REFERENCIA_AUSENTE", f"no se pudo leer una revisión: {exc}", args.ruta)
    alcance = f"{args.ruta}:{args.carpeta}"
    if paquete["estado"] == "bloqueado":
        salida, codigo = sobre(op, paquete, args.propuesta, alcance=alcance), 2
    else:
        estado, codigo, avisos = _por_examen(
            len(paquete["registros"]),
            "la propuesta no cambia ningún registro: no hay nada que aprobar",
            paquete["advertencias"],
        )
        paquete["advertencias"] = avisos
        resultado = {k: v for k, v in paquete.items() if k not in ("advertencias", "no_evaluado")}
        salida = sobre(op, {**resultado, "estado": estado}, args.propuesta, avisos, alcance, paquete["no_evaluado"])
        salida["valido_en"], salida["conocido_hasta"] = args.valido_en, args.conocido_hasta
    if args.texto:
        return presentar_aprobacion(paquete), codigo
    return salida, codigo


def _proponer(args):
    """Propone archivos del árbol de trabajo desde el clon del integrador; por defecto ensaya y no cambia nada.

    La rama, las carpetas, el modo de aprobación, el remoto y los recibos los fija la instalación, leída de HEAD. Sale
    con 3 si el ensayo necesita una aprobación que no se dio: el resultado trae el paquete (--texto lo presenta).
    """
    op = "proponer"
    error = _faltan(
        op,
        (("--instalacion", args.instalacion), ("--operacion-id", args.operacion_id), ("--archivos", args.archivos)),
    )
    if error:
        return error
    if args.rama_canonica or args.carpeta != "." or args.aprobacion or args.recibos or args.remoto:
        return _bloqueado(
            op, "la rama, las carpetas, el modo de aprobación, el remoto y los recibos de proponer los fija la instalación"
        )
    try:
        instalacion, _ = verificar_mod.instalacion_controlada(args.ruta, args.instalacion)
        res = proponer_mod.proponer(
            args.ruta,
            instalacion,
            operacion_id=args.operacion_id,
            archivos=args.archivos,
            actor=args.actor,
            efectos=_leer_json(args.efectos) if args.efectos else None,
            importaciones=_leer_json(args.importaciones) if args.importaciones else None,
            aprobaciones=_leer_json(args.aprobaciones) if args.aprobaciones else None,
            hasta=args.hasta,
            valido_en=args.valido_en,
        )
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        return _fallido(op, "ESQUEMA_INVALIDO", str(exc), args.ruta)
    estados = {"ensayado": 0, "integrado": 0, "subido": 0, "bloqueado": 2, "pendiente_de_aprobacion": 3}
    codigo = estados.get(res.get("estado"), 1)
    if args.texto and "paquete" in res:
        return presentar_aprobacion(res["paquete"]), codigo
    no_evaluado = [
        "autenticidad de las aprobaciones declaradas",
        "que el árbol de trabajo parta de la cabeza de la rama canónica",
        "aislamiento de los pasos posteriores",
    ]
    return sobre(op, res, res.get("revision_integrada"), alcance=args.ruta, no_evaluado=no_evaluado), codigo


def _arranque(args):
    """Arranque declarado de la raíz. El de GitHub sigue disponible como biblioteca."""
    error = _faltan(
        "arranque",
        (
            ("--rama-canonica", args.rama_canonica),
            ("--operacion-id", args.operacion_id),
            ("--base", args.base),
            ("--persona", args.persona),
            ("--roles", args.roles),
            ("--declaracion", args.declaracion),
            ("--recibos", args.recibos),
        ),
    )
    if error:
        return error
    try:
        declaracion = _leer_json(args.declaracion)
    except (OSError, ValueError) as exc:
        return _fallido("arranque", "ESQUEMA_INVALIDO", f"declaración ilegible: {exc}", args.declaracion)
    recibo = arrancar(
        args.ruta,
        rama=args.rama_canonica,
        carpeta=_carpetas(args),
        base_esperada=args.base,
        persona=args.persona,
        roles=args.roles.split(","),
        declaracion=declaracion,
        recibos=args.recibos,
        operacion_id=args.operacion_id,
    )
    codigo = {"arrancado": 0, "bloqueado": 2}.get(recibo.get("estado"), 1)
    return sobre("arranque", recibo, recibo.get("revision_integrada"), alcance=args.ruta), codigo


def _exportar_skills(args):
    """Escribe las skills empaquetadas bajo la ruta, con la versión de KBOL."""
    if args.skills is not None and not args.skills:
        return _bloqueado("exportar_skills", "--skills sin nombres: nada que exportar")
    try:
        res = exportar_skills(args.ruta, __version__, args.skills)
    except (OSError, ValueError) as exc:
        return _fallido("exportar_skills", "REFERENCIA_AUSENTE", f"no se pudieron exportar: {exc}", args.ruta)
    if res["estado"] == "bloqueado":
        return sobre("exportar_skills", res, alcance=args.ruta, no_evaluado=[]), 2
    avisos = [f"{r} ya estaba al día" for r in res["iguales"]]
    return sobre("exportar_skills", res, advertencias=avisos, alcance=args.ruta, no_evaluado=[]), 0


def _desvios(args):
    """Registros con historial editados fuera del flujo. Avisa y termina con 0: no bloquea."""
    try:
        res = desvios_mod(args.ruta, _carpetas(args), preparado=args.preparado, rama=args.rama_canonica)
    except (OSError, UnicodeDecodeError, subprocess.CalledProcessError) as exc:
        return _fallido("desvios", "REFERENCIA_AUSENTE", f"no se pudo leer la carpeta: {exc}", args.ruta)
    avisos = [
        f"{a['id']} ({a['ruta']}): {'difiere de lo integrado' if a['motivo'] == 'distinta' else 'sin huella'}"
        for a in res["avisos"]
    ]
    cobertura = res["cobertura"]
    if cobertura["estado"] == "bloqueado":
        errores = [h for h in cobertura["hallazgos"] if h["severidad"] == "error"]
        bloqueo = {"estado": "bloqueado", "codigo": errores[0]["codigo"], "motivo": "snapshot incoherente"}
        return sobre("desvios", {**bloqueo, "hallazgos": errores}, alcance=args.ruta), 2
    # Encontrar desvíos avisa y no bloquea. No haber comprobado ningún registro, o haber dejado fuera alguno
    # que no se pudo leer, es parcial: el estado no contradice a la cobertura.
    estado, codigo, avisos = _por_examen(
        res["comprobados"],
        "ningún registro con historial comprobado: ¿están bien la carpeta y la revisión?",
        cobertura["advertencias"] + avisos,
        cobertura["estado"] != "completo",
    )
    resultado = {"estado": estado, "comprobados": res["comprobados"], "avisos": res["avisos"]}
    no_evaluado = ["registros sin historial", "quien hizo la edición"]
    # Con la rama canónica, también los commits que cambian registros sin pasar por la puerta.
    # Avisan y no bloquean, como los desvíos.
    if args.rama_canonica and not args.preparado:
        fuera = commits_fuera_del_flujo(args.ruta, _carpetas(args), args.rama_canonica)
        resultado["commits_fuera_del_flujo"] = fuera["commits"]
        if fuera["evaluado"]:
            no_evaluado.append("commits de la rama canónica anteriores al primero de la puerta")
            avisos = avisos + [
                f"{c['commit'][:12]} ({c['correo']}): cambia registros sin pasar por la puerta" for c in fuera["commits"]
            ]
        else:
            no_evaluado.append("commits de la rama canónica: ilegible o sin commits de la puerta")
    else:
        no_evaluado.append("commits de la rama canónica")
    salida = sobre("desvios", resultado, advertencias=avisos, alcance=args.ruta, no_evaluado=no_evaluado)
    salida["cobertura"].update(_cobertura_de_carga(cobertura))
    return salida, codigo


def _enlaces(args):
    """Enlaces internos de los documentos Markdown de la raíz. Un enlace roto es `fallido`; la deuda declarada, no."""
    try:
        excluir, deuda = configuracion_enlaces(_leer_json(args.instalacion) if args.instalacion else {})
    except OSError as exc:
        return _fallido("enlaces", "REFERENCIA_AUSENTE", f"no se pudo leer la instalación: {exc}", args.instalacion)
    except ValueError as exc:
        return _fallido("enlaces", "ESQUEMA_INVALIDO", f"instalación mal formada: {exc}", args.instalacion)
    carpetas = _carpetas(args)
    try:
        res = comprobar_enlaces(args.ruta, carpetas if isinstance(carpetas, list) else [carpetas], excluir, deuda)
    except (OSError, ValueError) as exc:
        return _fallido("enlaces", "REFERENCIA_AUSENTE", str(exc), args.ruta)
    avisos = [f"{r}: no se pudo leer como UTF-8; sus enlaces no se revisaron" for r in res["ilegibles"]]
    avisos += [f"{d['documento']}: «{d['destino']}» ya no falla: retíralo de la deuda" for d in res["deuda_sobrante"]]
    no_evaluado = [
        "enlaces externos",
        "destinos fuera de la raíz",
        "fragmentos de archivos que no son Markdown",
        "documentos excluidos por la instalación",
    ]
    alcance = f"{args.ruta}:{args.carpeta}"
    if res["errores"]:
        motivo = f"{len(res['errores'])} enlace(s) o ancla(s) que no se resuelven"
        resultado = {"estado": "fallido", "codigo": "REFERENCIA_AUSENTE", "motivo": motivo, **res}
        return sobre("enlaces", resultado, advertencias=avisos, alcance=alcance, no_evaluado=no_evaluado), 1
    estado, codigo, avisos = _por_examen(
        res["documentos"],
        "ningún documento Markdown revisado: ¿están bien la raíz y la carpeta?",
        avisos,
        bool(res["ilegibles"]),
    )
    return sobre(
        "enlaces", {"estado": estado, **res}, advertencias=avisos, alcance=alcance, no_evaluado=no_evaluado
    ), codigo


def _integridad(args):
    """Integridad de las fuentes. Una fuente alterada o ausente es `fallido`; una sin comprobar, `parcial`."""
    almacen = Path(args.almacen) if args.almacen else None
    try:
        res = comprobar_integridad(args.ruta, _carpetas(args), almacen)
    except (OSError, UnicodeDecodeError, subprocess.CalledProcessError) as exc:
        return _fallido("integridad", "REFERENCIA_AUSENTE", f"no se pudo leer la carpeta: {exc}", args.ruta)
    cobertura = res["cobertura"]
    if cobertura["estado"] == "bloqueado":
        errores = [h for h in cobertura["hallazgos"] if h["severidad"] == "error"]
        bloqueo = {"estado": "bloqueado", "codigo": errores[0]["codigo"], "motivo": "snapshot incoherente"}
        return sobre("integridad", {**bloqueo, "hallazgos": errores}, alcance=args.ruta), 2
    filas, recuento = res["fuentes"], res["recuento"]
    avisos = cobertura["advertencias"] + [
        f"{f['id']} ({f['ubicacion']}): {f['estado']}: {f['causa']}" for f in filas if f["estado"] != "coincide"
    ]
    rotas = recuento["alterada"] + recuento["ausente"]
    if rotas:
        # El código dice la causa y el estado, el resultado operativo: rota no es lo mismo que sin comprobar.
        motivo = f"{rotas} fuente(s) con el contenido alterado o ausente"
        resultado, codigo = {"estado": "fallido", "codigo": "INTEGRIDAD_ROTA", "motivo": motivo}, 1
    else:
        sin_comprobar = bool(recuento["no_comprobada"])
        estado, codigo, avisos = _por_examen(
            len(filas),
            "ninguna fuente en las carpetas: ¿están bien escritas?",
            avisos,
            sin_comprobar or cobertura["estado"] != "completo",
        )
        resultado = {"estado": estado}
        if sin_comprobar:
            resultado["codigo"] = "INTEGRIDAD_NO_COMPROBADA"
    no_evaluado = ["última comprobación válida de cada fuente", "vigencia de la fuente", "calidad de las derivaciones"]
    salida = sobre(
        "integridad",
        {**resultado, "fuentes": filas, "recuento": recuento},
        advertencias=avisos,
        alcance=f"{args.ruta}:{args.carpeta}",
        no_evaluado=no_evaluado,
    )
    salida["cobertura"].update(_cobertura_de_carga(cobertura))
    return salida, codigo


def _citas(args):
    """Resuelve las citas (`sources`) de los registros. Salida 3 si alguna está rota o es inconsistente."""
    almacen = Path(args.almacen) if args.almacen else None
    carpetas = _carpetas(args)
    try:
        res = comprobar_citas(Path(args.ruta), carpetas if isinstance(carpetas, list) else [carpetas], almacen)
    except OSError as exc:
        return _fallido("citas", "REFERENCIA_AUSENTE", f"no se pudo leer la carpeta: {exc}", args.ruta)
    malas = res["recuento"]["rota"] + res["recuento"]["inconsistente"]
    avisos = [
        f"{f['registro']}#{f['source']}: {f['estado']}: {f['motivo']}"
        for f in res["filas"]
        if f["estado"] != "resuelta"
    ]
    estado, codigo, avisos = _por_examen(
        len(res["filas"]), "ninguna cita encontrada en las carpetas: ¿están bien escritas?", avisos, bool(malas)
    )
    no_evaluado = ["respaldo semántico de la cita", "vigencia de la fuente", "originales ausentes del almacén"]
    return sobre(
        "citas", {"estado": estado, **res}, advertencias=avisos, alcance=args.ruta, no_evaluado=no_evaluado
    ), codigo


def _sesion(args):
    """Órdenes para los hooks de una instalación: `--evento` inicio, parar o commit. Con --texto, solo
    lo que el adaptador inyecta en la sesión; un fallo de la orden sale siempre como sobre."""
    error = _faltan("sesion", (("--evento", args.evento), ("--instalacion", args.instalacion)))
    if error:
        return error
    try:
        res = sesion_mod.ejecutar(
            args.evento,
            args.ruta,
            args.instalacion,
            tarea=args.tarea,
            valido_en=args.valido_en,
            origen=args.origen,
            rutas=args.rutas,
        )
    except ValueError as exc:
        return _fallido("sesion", "ESQUEMA_INVALIDO", str(exc), args.ruta)
    except (OSError, subprocess.CalledProcessError) as exc:
        return _fallido("sesion", "REFERENCIA_AUSENTE", str(exc), args.ruta)
    if args.texto:
        return res["texto"], res["codigo"]
    salida = sobre(
        "sesion", res["resultado"], res["revision"], res["advertencias"], res["alcance"], res["no_evaluado"]
    )
    salida["valido_en"] = res["valido_en"]
    salida["cobertura"].update(res["cobertura"])
    return salida, res["codigo"]


def _sin_repetidas(pares):
    claves = [k for k, _ in pares]
    if len(claves) != len(set(claves)):
        raise ValueError(f"clave JSON repetida en {claves}")
    return dict(pares)


def _leer_json(ruta):
    return json.loads(Path(ruta).read_text(encoding="utf-8"), object_pairs_hook=_sin_repetidas)


def main(argv=None):
    p = argparse.ArgumentParser(prog="kbol", description="KBOL: núcleo KB-DPP")
    p.add_argument("--version", action="version", version=f"kbol {__version__}")
    p.add_argument("operacion", choices=HABILITADAS + NO_HABILITADAS)
    p.add_argument("ruta", nargs="?")
    p.add_argument("--revision")
    p.add_argument("--skills", nargs="*", default=None, help="skills que exportar; todas si no se dan (exportar_skills)")
    p.add_argument("--modo", choices=["propuesta", "canonico", "intercambio"], default="propuesta")
    p.add_argument("--efectos", help="JSON con los efectos solicitados (digest y proponer)")
    p.add_argument("--valido-en", dest="valido_en", help="instante del dominio consultado, con zona")
    p.add_argument("--conocido-hasta", dest="conocido_hasta", help="corte del historial admitido, con zona")
    p.add_argument("--carpeta", default=".", help="carpeta de registros; varias, separadas por comas")
    p.add_argument("--ids", nargs="*", default=[], help="IDs que consolidar, consultar o, en soporte, examinar")
    p.add_argument("--consulta", help="texto que se busca (buscar)")
    p.add_argument(
        "--incluir", nargs="*", default=[], choices=sorted(_INCLUIR), help="buscar: muestra también estas clases"
    )
    p.add_argument("--limite", type=int, default=10, help="candidatos que muestra buscar")
    p.add_argument("--llano", action="store_true", help="consultar, consolidar y buscar: respuesta en prosa llana")
    p.add_argument("--con-ids", dest="con_ids", action="store_true", help="con --llano, muestra los IDs y anclas")
    p.add_argument("--antes-valido-en", dest="antes_valido_en", help="soporte: instante del dominio del primer corte")
    p.add_argument("--antes-conocido-hasta", dest="antes_conocido_hasta", help="soporte: conocimiento del primer corte")
    p.add_argument("--base", help="revisión de partida (impacto, integrar, preparar_aprobacion)")
    p.add_argument("--tarea", help="id de la tarea (relevo y preparar_contexto)")
    p.add_argument("--guardar", help="JSON con el relevo que se guarda antes de leerlo")
    p.add_argument(
        "--rama-canonica",
        dest="rama_canonica",
        help="rama canónica: obligatoria en integrar y arranque; en el relevo, main si no se da",
    )
    p.add_argument("--aprobacion", choices=MODOS, help="qué exige aprobación (integrar); toda si no se da")
    p.add_argument("--actor", help="actor de la operación, que firma sus eventos (integrar)")
    p.add_argument("--objetivo", help="objetivo de la tarea; si falta, el del relevo")
    p.add_argument("--ambito", help="ámbito del paquete de contexto")
    p.add_argument(
        "--instalacion",
        help="JSON con la configuración de la instalación; en las consultas y migrar, solo su formato_heredado",
    )
    p.add_argument("--presupuesto", type=int, default=30, help="elementos del paquete de contexto")
    p.add_argument("--heredados-carpeta", dest="heredados_carpeta", help="carpeta del formato heredado (pendientes)")
    p.add_argument("--texto", action="store_true", help="presenta el paquete como texto breve")
    p.add_argument("--verificacion", help="id de una verificación declarada en la instalación")
    p.add_argument(
        "--operacion-id",
        dest="operacion_id",
        help="operacion_id de una integración, su paquete de aprobación o un arranque",
    )
    p.add_argument("--propuesta", help="SHA del commit propuesto (integrar, preparar_aprobacion)")
    p.add_argument("--aprobaciones", help="JSON con la lista de aprobaciones declaradas (integrar)")
    p.add_argument("--recibos", help="directorio de recibos, fuera del árbol canónico")
    p.add_argument("--remoto", help="remoto con el que la base y la rama tienen que estar al día (integrar)")
    p.add_argument("--persona", help="persona de la raíz (arranque)")
    p.add_argument("--roles", help="roles de la raíz, separados por comas (arranque)")
    p.add_argument("--declaracion", help="JSON con la declaración de la raíz (arranque)")
    p.add_argument("--almacen", help="almacén de originales y representaciones direccionado por contenido (citas)")
    p.add_argument("--preparado", action="store_true", help="compara el índice de git, no el disco (desvios)")
    p.add_argument("--evento", choices=sesion_mod.EVENTOS, help="evento del hook que llama (sesion)")
    p.add_argument("--origen", help="origen del inicio de sesión; con compact añade el trabajo de la tarea en git")
    p.add_argument("--rutas", nargs="*", help="rutas a las que se limita la validación (sesion --evento parar)")
    p.add_argument(
        "--heredados",
        action="store_true",
        help="lee también el formato heredado (el formato por defecto o el que declare --instalacion), aparte y sin que rija",
    )
    p.add_argument("--archivos", nargs="+", default=[], help="registros que se proponen, relativos a la raíz (proponer)")
    p.add_argument("--importaciones", help="JSON con las importaciones de la solicitud (proponer)")
    p.add_argument(
        "--hasta",
        choices=proponer_mod.HASTA,
        default="ensayo",
        help="hasta dónde llega proponer: ensayo, integrar en el clon del integrador o subir al remoto",
    )
    salida, codigo = ejecutar(p.parse_intermixed_args(argv))
    sys.stdout.reconfigure(encoding="utf-8")
    print(salida if isinstance(salida, str) else json.dumps(salida, ensure_ascii=False))
    return codigo


if __name__ == "__main__":
    raise SystemExit(main())
