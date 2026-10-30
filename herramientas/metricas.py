"""Reporte de métricas estructurales (sección 4.2): CC, Ca, Ce, I, A, D y ley de Deméter.

Se calcula por componente (los paquetes de nucleo, cada plug-in, presentacion y persistencia):
  Ca  acoplamiento aferente: cuántos componentes internos lo importan.
  Ce  acoplamiento eferente: cuántos componentes internos importa.
  I   inestabilidad = Ce / (Ca + Ce).
  A   abstracción = clases abstractas (Protocol, ABC o con @abstractmethod) / clases.
  D   distancia a la secuencia principal = |A + I - 1| (Richards y Ford, cap. 3).
Deméter: llamadas sobre el resultado de otra llamada a un método (x.f().g()), sin contar `self`,
los objetos recién creados (Clase(...).f()) ni los métodos de tipos básicos (str, dict, list, rutas
y cursores), que no exponen estructura ajena.

Uso:  python herramientas/metricas.py [--salida archivo.md] [--exigir]
Con --exigir el proceso falla si un plug-in se aleja de la secuencia principal (D > 0,5) o si un
evaluador de combinaciones supera CC 10; así el CI lo puede usar como fitness function.
"""
from __future__ import annotations

import argparse
import ast
import sys
from collections import defaultdict
from pathlib import Path

from radon.complexity import cc_visit

RAIZ = Path(__file__).resolve().parents[1] / "src" / "juegocartas"
PAQUETE = "juegocartas"
UMBRAL_D_PLUGIN = 0.5
UMBRAL_CC_EVALUACION = 10
EVALUACION = ("nucleo/evaluacion", "nucleo/contrato/combinaciones.py", "plugins")  # ternas, cuartas y cierres
BASICOS = {"strip", "split", "rsplit", "replace", "lower", "upper", "join", "format", "isoformat", "items",
           "values", "keys", "get", "read_text", "fetchone", "fetchall", "execute", "copy", "encode",
           "decode", "startswith", "endswith", "count", "index", "resolve", "exists", "json", "group",
           "setdefault", "append"}


def componente(archivo: Path) -> str:
    partes = archivo.relative_to(RAIZ).with_suffix("").parts
    if partes[0] in ("nucleo", "plugins") and len(partes) > 2:
        return ".".join(partes[:2])
    return partes[0]


def importados(arbol: ast.AST) -> set[str]:
    nombres = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.ImportFrom) and nodo.module and nodo.level == 0:
            nombres.add(nodo.module)
        elif isinstance(nodo, ast.Import):
            nombres.update(a.name for a in nodo.names)
    return {n.removeprefix(PAQUETE + ".") for n in nombres if n.startswith(PAQUETE + ".")}


def destino(modulo: str, componentes: set[str]) -> str | None:
    partes = modulo.split(".")
    for largo in (2, 1):
        if ".".join(partes[:largo]) in componentes:
            return ".".join(partes[:largo])
    return None


def es_abstracta(clase: ast.ClassDef) -> bool:
    bases = {ast.unparse(b).split(".")[-1].split("[")[0] for b in clase.bases}
    if bases & {"Protocol", "ABC"} or any(ast.unparse(k.value) == "ABCMeta" for k in clase.keywords):
        return True
    return any(isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
               and any(ast.unparse(d).endswith("abstractmethod") for d in n.decorator_list) for n in clase.body)


def demeter(arbol: ast.AST) -> list[tuple[int, str]]:
    """x.f().g(): se habla con un desconocido que devolvió otro objeto."""
    hallazgos = []
    for nodo in ast.walk(arbol):
        if not (isinstance(nodo, ast.Attribute) and isinstance(nodo.value, ast.Call)):
            continue
        interna = nodo.value.func
        if not isinstance(interna, ast.Attribute) or nodo.attr in BASICOS or interna.attr in BASICOS:
            continue
        if isinstance(interna.value, ast.Name) and interna.value.id in ("self", "cls"):
            continue
        if interna.attr[:1].isupper():  # Clase(...).metodo(): el objeto lo acaba de crear, es "amigo"
            continue
        hallazgos.append((nodo.lineno, ast.unparse(nodo)[:70]))
    return hallazgos


def medir() -> dict:
    archivos = [a for a in RAIZ.rglob("*.py") if "__pycache__" not in a.parts and a.name != "__init__.py"]
    componentes = {componente(a) for a in archivos}
    ce, ca = defaultdict(set), defaultdict(set)
    clases, abstractas, deme, cc = defaultdict(int), defaultdict(int), defaultdict(list), []
    for archivo in archivos:
        origen, texto = componente(archivo), archivo.read_text(encoding="utf-8")
        arbol = ast.parse(texto)
        for modulo in importados(arbol):
            otro = destino(modulo, componentes)
            if otro and otro != origen:
                ce[origen].add(otro)
                ca[otro].add(origen)
        for clase in (n for n in ast.walk(arbol) if isinstance(n, ast.ClassDef)):
            clases[origen] += 1
            abstractas[origen] += es_abstracta(clase)
        relativo = archivo.relative_to(RAIZ).as_posix()
        deme[origen] += [(f"{relativo}:{linea}", codigo) for linea, codigo in demeter(arbol)]
        cc += [(relativo, b.fullname, b.complexity) for b in cc_visit(texto)]
    filas = []
    for c in sorted(componentes):
        n_ca, n_ce = len(ca[c]), len(ce[c])
        inestable = n_ce / (n_ca + n_ce) if n_ca + n_ce else 0.0
        abstracto = abstractas[c] / clases[c] if clases[c] else 0.0
        filas.append({"componente": c, "Ca": n_ca, "Ce": n_ce, "I": inestable, "A": abstracto,
                      "D": abs(abstracto + inestable - 1), "clases": clases[c], "demeter": deme[c],
                      "depende_de": sorted(ce[c])})
    return {"filas": filas, "cc": cc}


def zona(f: dict) -> str:
    if f["D"] <= 0.3:
        return "cerca de la secuencia principal"
    return "zona del dolor (estable y concreto)" if f["I"] + f["A"] < 1 else "zona de inutilidad (abstracto y sin uso)"


def reporte(m: dict) -> str:
    lineas = ["# Métricas estructurales del MVP", "",
              "| Componente | Ca | Ce | I | A | D | Zona | Deméter |", "|---|---:|---:|---:|---:|---:|---|---:|"]
    for f in m["filas"]:
        lineas.append(f"| {f['componente']} | {f['Ca']} | {f['Ce']} | {f['I']:.2f} | {f['A']:.2f} | {f['D']:.2f} "
                      f"| {zona(f)} | {len(f['demeter'])} |")
    evaluacion = [x for x in m["cc"] if x[0].startswith(EVALUACION)]
    todos = [x[2] for x in m["cc"]]
    lineas += ["", "## Complejidad ciclomática (radon)", "",
               f"- Bloques medidos: {len(todos)}; promedio {sum(todos) / len(todos):.2f}; máximo {max(todos)}.",
               f"- Evaluación de ternas, cuartas y cierres: {len(evaluacion)} bloques, promedio "
               f"{sum(x[2] for x in evaluacion) / len(evaluacion):.2f}, máximo {max(x[2] for x in evaluacion)} "
               f"(umbral {UMBRAL_CC_EVALUACION}, deseable < 5).", "",
               "| Archivo | Bloque | CC |", "|---|---|---:|"]
    lineas += [f"| {a} | {b} | {c} |" for a, b, c in sorted(m["cc"], key=lambda x: -x[2])[:10]]
    lineas += ["", "## Ley de Deméter: llamadas encadenadas a objetos ajenos", ""]
    hallazgos = [(lugar, codigo) for f in m["filas"] for lugar, codigo in f["demeter"]]
    lineas += [f"- `{lugar}`: `{codigo}`" for lugar, codigo in hallazgos] or ["- Ninguna."]
    lineas += ["", "## Dependencias entre componentes (Ce)", ""]
    lineas += [f"- **{f['componente']}** → {', '.join(f['depende_de']) or '(ninguna)'}" for f in m["filas"]]
    return "\n".join(lineas) + "\n"


def violaciones(m: dict) -> list[str]:
    malas = [f"{f['componente']}: D = {f['D']:.2f} > {UMBRAL_D_PLUGIN}" for f in m["filas"]
             if f["componente"].startswith("plugins.") and f["D"] > UMBRAL_D_PLUGIN]
    malas += [f"{a} {b}: CC {c} > {UMBRAL_CC_EVALUACION}" for a, b, c in m["cc"]
              if a.startswith(EVALUACION) and c > UMBRAL_CC_EVALUACION]
    return malas


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--salida", type=Path)
    parser.add_argument("--exigir", action="store_true")
    args = parser.parse_args()
    m = medir()
    texto = reporte(m)
    if args.salida:
        args.salida.parent.mkdir(parents=True, exist_ok=True)
        args.salida.write_text(texto, encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    print(texto)
    malas = violaciones(m) if args.exigir else []
    for mala in malas:
        print("VIOLACIÓN:", mala, file=sys.stderr)
    return 1 if malas else 0


if __name__ == "__main__":
    sys.exit(main())
