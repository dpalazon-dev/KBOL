"""Enlaces, fragmentos y anclas de los documentos Markdown (`kbol enlaces`)."""

import json
import subprocess

import pytest

from kbol import enlaces as en
from kbol.cli import main

GIT = ["-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false"]

GUIA = "\n".join(
    [
        "---",
        "title: Guía",
        "description: x",
        "---",
        "",
        "# Guía de prueba",
        "",
        '<a id="puerta-integracion"></a>',
        "## Cómo se integra (paso 1)",
        "",
        "## Notas",
        "## Notas",
        "",
    ]
)


def revisar(docs, extra=(), deuda=frozenset()):
    """Resultado de un árbol en memoria: existen sus documentos y las rutas de `extra`."""
    return en.revisar(docs, set(docs) | set(extra), docs.get, set(deuda))


def mensajes(docs, **kw):
    return [(e["ruta"], e["linea"], e["mensaje"]) for e in revisar(docs, **kw)["errores"]]


# ── Anclas ──────────────────────────────────────────────────────────────────


def test_anclas_de_titulos_al_estilo_de_github_y_explicitas():
    anclas, repetidas = en.anclas(GUIA)
    assert {"guía-de-prueba", "cómo-se-integra-paso-1", "notas", "notas-1", "puerta-integracion"} <= anclas
    assert repetidas == []


def test_la_cabecera_yaml_no_crea_titulos():
    anclas, _ = en.anclas(GUIA)
    assert not any("title" in a or "description" in a for a in anclas)


def test_titulo_con_codigo_y_enlace():
    anclas, _ = en.anclas("## Uso de `kbol validar` y [KBOL](x.md)\n")
    assert "uso-de-kbol-validar-y-kbol" in anclas


def test_ancla_explicita_repetida_se_senala():
    _, repetidas = en.anclas('<a id="x"></a>\n\ntexto\n\n<a id="x"></a>\n')
    assert repetidas == [(5, "x")]


def test_id_y_name_en_la_misma_etiqueta_es_una_sola_ancla():
    anclas, repetidas = en.anclas('<a name="x" id="x"></a>\n')
    assert "x" in anclas and repetidas == []


def test_solo_id_y_name_de_a_son_anclas():
    anclas, _ = en.anclas('<div data-id="foo"></div>\n\n<input name="bar">\n\n<span id="baz"></span>\n')
    assert "foo" not in anclas and "bar" not in anclas and "baz" in anclas


def test_la_marca_de_una_clausula_es_un_ancla():
    anclas, repetidas = en.anclas('<clausula id="C1">\nLos martes.\n</clausula>\n\n<clausula id="C2">\nNo.\n</clausula>\n')
    assert {"C1", "C2"} <= anclas and repetidas == []


def test_slug_conserva_marcas_y_quita_simbolos():
    assert en.slug("⚠️ Aviso") == "️-aviso"  # el emoji se va; su selector de variante (una marca) queda
    assert en.slug("Qué es (y qué no)") == "qué-es-y-qué-no"
    assert en.slug("snake_case y guion-medio") == "snake_case-y-guion-medio"


# ── Enlaces ─────────────────────────────────────────────────────────────────


def test_enlaces_ignoran_bloques_y_codigo_en_linea():
    texto = "\n".join(
        [
            "[a](a.md) y `[b](b.md)`",
            "```markdown",
            "[c](c.md)",
            "```",
            "    [d](d.md)",
            "",
            "![imagen](img.png) y [e][ref]",
            "",
            "[ref]: e.md",
        ]
    )
    assert en.enlaces(texto) == [(1, "a.md"), (7, "img.png"), (7, "e.md")]


def test_enlace_en_un_parrafo_de_varias_lineas_da_su_linea():
    assert en.enlaces("Primera línea\nsegunda con [x](x.md)\n") == [(2, "x.md")]


def test_la_linea_no_se_confunde_con_texto_parecido_ni_con_un_enlace_repetido():
    assert en.enlaces("ver data.md y\n[a](a.md)\n") == [(2, "a.md")]
    assert en.enlaces("[x](a.md) y\n[y](a.md)\n") == [(1, "a.md"), (2, "a.md")]


def test_enlace_valido_con_fragmento_no_da_error():
    docs = {
        "docs/guia.md": GUIA,
        "docs/a.md": "[g](guia.md#puerta-integracion), [t](guia.md#cómo-se-integra-paso-1), [n](guia.md#notas-1)\n",
    }
    res = revisar(docs)
    assert res["errores"] == [] and res["enlaces"] == 3


def test_fragmento_inexistente():
    docs = {"docs/guia.md": GUIA, "docs/a.md": "Ver [g](guia.md#no-existe).\n"}
    assert mensajes(docs) == [("docs/a.md", 1, "«guia.md#no-existe»: docs/guia.md no tiene el ancla «no-existe»")]


def test_fragmento_en_el_propio_documento():
    docs = {"docs/a.md": "# A\n\n## Uno\n\n[bien](#uno) y [mal](#dos)\n"}
    assert mensajes(docs) == [("docs/a.md", 5, "«#dos»: docs/a.md no tiene el ancla «dos»")]


def test_fragmento_con_otras_mayusculas():
    docs = {"docs/guia.md": GUIA, "docs/a.md": "[g](guia.md#Notas)\n"}
    assert [m[2] for m in mensajes(docs)] == ["«guia.md#Notas»: docs/guia.md no tiene el ancla «Notas»"]


def test_fragmento_de_un_archivo_que_no_es_markdown_no_se_comprueba():
    docs = {"docs/a.md": "[código](../src/x.py#L10)\n"}
    assert mensajes(docs, extra=("src/x.py",)) == []


def test_ruta_inexistente_y_con_otras_mayusculas():
    docs = {"docs/a.md": "[x](no.md) [y](Guia.md)\n", "docs/guia.md": "# G\n"}
    assert mensajes(docs) == [
        ("docs/a.md", 1, "«no.md»: docs/no.md no existe"),
        ("docs/a.md", 1, "«Guia.md»: docs/Guia.md no existe; se escribe docs/guia.md"),
    ]


def test_enlaces_con_titulo_por_referencia_y_con_espacios():
    docs = {"docs/m/a.md": '[t](no.md "Título") [r][ref] [s](<no con espacio.md>) [d](docs/b.md)\n\n[ref]: no-ref.md\n'}
    assert [m[2] for m in mensajes(docs, extra=("docs/b.md",))] == [
        "«no.md»: docs/m/no.md no existe",
        "«no-ref.md»: docs/m/no-ref.md no existe",
        "«no con espacio.md»: docs/m/no con espacio.md no existe",
        "«docs/b.md»: docs/m/docs/b.md no existe",
    ]


def test_enlace_a_carpeta_a_la_raiz_externo_y_fuera_de_la_raiz():
    docs = {
        "docs/a.md": "[c](manual/) [r](../) [w](https://x.org/a#b) [m](mailto:a@b.c) [f](../../fuera.md)\n",
        "README.md": "[repo](.)\n",
    }
    assert mensajes(docs, extra=("docs/manual/r.md",)) == []


def test_ruta_desde_la_raiz_y_con_consulta():
    docs = {"docs/a.md": "[x](/docs/b.md) [y](b.md?plain=1) [z](/no.md)\n", "docs/b.md": "# B\n"}
    assert [m[2] for m in mensajes(docs)] == ["«/no.md»: no.md no existe"]


def test_ruta_absoluta_local():
    docs = {"docs/a.md": "[x](C:/Users/alguien/x.md)\n"}
    assert mensajes(docs) == [("docs/a.md", 1, "«C:/Users/alguien/x.md»: ruta absoluta local; usa una ruta relativa")]


def test_ruta_codificada_se_resuelve():
    docs = {"docs/a.md": "[x](mi%20guia.md)\n", "docs/mi guia.md": "# M\n"}
    assert mensajes(docs) == []


def test_ancla_explicita_repetida_es_un_error():
    docs = {"docs/a.md": '<a id="x"></a>\n\n<a id="x"></a>\n'}
    assert mensajes(docs) == [("docs/a.md", 3, "el ancla explícita «x» está repetida")]


def test_la_deuda_declarada_no_es_un_error_y_se_sabe_cual_se_uso():
    docs = {"docs/a.md": "[x](no.md)\n"}
    res = revisar(docs, deuda={("docs/a.md", "no.md"), ("docs/b.md", "z.md")})
    assert res["errores"] == [] and res["deuda_usada"] == {("docs/a.md", "no.md")}


# ── Configuración de la instalación ─────────────────────────────────────────


def test_configuracion_vacia_y_declarada():
    assert en.configuracion({}) == ([], set())
    instalacion = {
        "proyecto": "p",
        "enlaces": {"excluir": ["docs/originales/", ".\\copias"], "deuda": [{"documento": "a.md", "destino": "../x.md"}]},
    }
    assert en.configuracion(instalacion) == (["docs/originales", "copias"], {("a.md", "../x.md")})


@pytest.mark.parametrize(
    "declarado",
    [
        [],
        {"otra": 1},
        {"excluir": "docs"},
        {"excluir": [""]},
        {"excluir": ["."]},
        {"deuda": [{"documento": "a.md"}]},
        {"deuda": [{"documento": "a.md", "destino": "x.md", "motivo": "m"}]},
        {"deuda": [{"documento": "a.md", "destino": 3}]},
    ],
)
def test_configuracion_mal_formada(declarado):
    with pytest.raises(ValueError):
        en.configuracion({"enlaces": declarado})


# ── Sobre un repositorio ────────────────────────────────────────────────────


def escribir(raiz, ruta, texto):
    archivo = raiz / ruta
    archivo.parent.mkdir(parents=True, exist_ok=True)
    archivo.write_bytes(texto.encode("utf-8") if isinstance(texto, str) else texto)


@pytest.fixture
def repo(tmp_path):
    raiz = tmp_path / "repo"
    subprocess.run(["git", "init", "-q", "-b", "main", str(raiz)], check=True)
    escribir(raiz, ".gitignore", "ignorado/\n")
    escribir(raiz, "README.md", "# Proyecto\n\n[guía](docs/guia.md#notas) y [código](src/x.py)\n")
    escribir(raiz, "docs/guia.md", "# Guía\n\n## Notas\n\n[arriba](../README.md#proyecto)\n")
    escribir(raiz, "src/x.py", "x = 1\n")
    subprocess.run(["git", "-C", str(raiz), *GIT, "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(raiz), *GIT, "commit", "-q", "-m", "base"], check=True)
    return raiz


def kb(capsys, *args):
    codigo = main(list(args))
    return codigo, json.loads(capsys.readouterr().out)


def test_un_repositorio_sin_enlaces_rotos(repo):
    res = en.comprobar(repo)
    assert res["documentos"] == 2 and res["enlaces"] == 3 and res["errores"] == [] and res["ilegibles"] == []


def test_lo_nuevo_sin_ignorar_existe_y_lo_ignorado_no(repo):
    escribir(repo, "docs/nuevo.md", "[a](guia.md) [b](../ignorado/x.md)\n")
    escribir(repo, "ignorado/x.md", "[roto](no.md)\n")
    res = en.comprobar(repo)
    assert res["documentos"] == 3
    assert [(e["ruta"], e["destino"]) for e in res["errores"]] == [("docs/nuevo.md", "../ignorado/x.md")]


def test_un_archivo_borrado_del_disco_ya_no_existe(repo):
    (repo / "src" / "x.py").unlink()
    assert [e["destino"] for e in en.comprobar(repo)["errores"]] == ["src/x.py"]


def test_solo_se_revisan_las_carpetas_pedidas_pero_los_destinos_son_de_toda_la_raiz(repo):
    escribir(repo, "README.md", "# Proyecto\n\n[roto](no.md)\n")
    res = en.comprobar(repo, ["docs"])
    assert res["documentos"] == 1 and res["errores"] == []  # docs/guia.md enlaza README.md, fuera de la carpeta
    with pytest.raises(FileNotFoundError):
        en.comprobar(repo, ["no-existe"])


def test_lo_excluido_no_se_revisa_pero_se_puede_enlazar(repo):
    escribir(repo, "copias/ajeno.md", "# Ajeno\n\n[roto](donde-estaba.md)\n")
    escribir(repo, "docs/cita.md", "[copia](../copias/ajeno.md#ajeno)\n")
    assert [e["ruta"] for e in en.comprobar(repo)["errores"]] == ["copias/ajeno.md"]
    res = en.comprobar(repo, excluir=["copias"])
    assert res["errores"] == [] and res["documentos"] == 3


def test_la_deuda_que_ya_no_falla_sobra(repo):
    escribir(repo, "docs/viejo.md", "[x](no.md)\n")
    deuda = {("docs/viejo.md", "no.md"), ("docs/guia.md", "../README.md#proyecto")}
    res = en.comprobar(repo, deuda=deuda)
    assert res["errores"] == []
    assert res["deuda_usada"] == [{"documento": "docs/viejo.md", "destino": "no.md"}]
    assert res["deuda_sobrante"] == [{"documento": "docs/guia.md", "destino": "../README.md#proyecto"}]


def test_un_documento_que_no_es_utf8_no_se_da_por_revisado(repo):
    escribir(repo, "docs/latin.md", "[x](no.md) caf\xe9\n".encode("latin-1"))
    res = en.comprobar(repo)
    assert res["ilegibles"] == ["docs/latin.md"] and res["errores"] == []


def test_fuera_de_git_no_se_sabe_que_existe(tmp_path):
    (tmp_path / "a.md").write_text("[x](b.md)\n", encoding="utf-8")
    with pytest.raises(ValueError, match="no es un árbol de trabajo de git"):
        en.comprobar(tmp_path)


def test_cli_completado_con_el_sobre(repo, capsys):
    codigo, out = kb(capsys, "enlaces", str(repo))
    assert codigo == 0 and out["operacion"] == "enlaces" and out["resultado"]["estado"] == "completado", out
    assert out["resultado"]["documentos"] == 2 and out["resultado"]["enlaces"] == 3
    assert "enlaces externos" in out["cobertura"]["no_evaluado"]


def test_cli_un_enlace_roto_es_fallido(repo, capsys):
    escribir(repo, "docs/guia.md", "# Guía\n\n[x](no.md)\n")
    codigo, out = kb(capsys, "enlaces", str(repo), "--carpeta", "docs")
    assert codigo == 1 and out["resultado"]["estado"] == "fallido", out
    assert out["resultado"]["codigo"] == "REFERENCIA_AUSENTE"
    assert out["resultado"]["errores"] == [
        {"ruta": "docs/guia.md", "linea": 3, "destino": "no.md", "mensaje": "«no.md»: docs/no.md no existe"}
    ]


def test_cli_la_deuda_y_las_exclusiones_salen_de_la_instalacion(repo, tmp_path, capsys):
    escribir(repo, "docs/viejo.md", "[x](no.md)\n")
    escribir(repo, "copias/ajeno.md", "[roto](donde-estaba.md)\n")
    instalacion = tmp_path / "instalacion.json"
    declarado = {
        "excluir": ["copias"],
        "deuda": [{"documento": "docs/viejo.md", "destino": "no.md"}, {"documento": "README.md", "destino": "src/x.py"}],
    }
    instalacion.write_text(json.dumps({"proyecto": "p", "enlaces": declarado}), encoding="utf-8")
    codigo, out = kb(capsys, "enlaces", str(repo), "--instalacion", str(instalacion))
    assert codigo == 0 and out["resultado"]["estado"] == "completado", out
    assert out["resultado"]["deuda_usada"] == [{"documento": "docs/viejo.md", "destino": "no.md"}]
    assert any("README.md" in a and "ya no falla" in a for a in out["advertencias"])


def test_cli_una_instalacion_mal_formada_no_revisa_nada(repo, tmp_path, capsys):
    instalacion = tmp_path / "instalacion.json"
    instalacion.write_text(json.dumps({"enlaces": {"deuda": "todo"}}), encoding="utf-8")
    codigo, out = kb(capsys, "enlaces", str(repo), "--instalacion", str(instalacion))
    assert codigo == 1 and out["resultado"]["codigo"] == "ESQUEMA_INVALIDO", out


def test_cli_un_documento_ilegible_es_parcial(repo, capsys):
    escribir(repo, "docs/latin.md", "caf\xe9\n".encode("latin-1"))
    codigo, out = kb(capsys, "enlaces", str(repo))
    assert codigo == 3 and out["resultado"]["estado"] == "parcial", out
    assert any("docs/latin.md" in a for a in out["advertencias"])


def test_cli_fuera_de_git_o_sin_la_carpeta_es_fallido(tmp_path, repo, capsys):
    codigo, out = kb(capsys, "enlaces", str(tmp_path))
    assert codigo == 1 and out["resultado"]["codigo"] == "REFERENCIA_AUSENTE", out
    codigo, out = kb(capsys, "enlaces", str(repo), "--carpeta", "no-existe")
    assert codigo == 1 and out["resultado"]["codigo"] == "REFERENCIA_AUSENTE", out
