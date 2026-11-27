"""LCOM4 por clase (Hitz y Montazeri): componentes conexas entre métodos que comparten atributos o se llaman.

LCOM4 = 1 es una clase cohesiva; > 1 sugiere partirla. Se ignoran clases sin métodos de instancia (protocolos, datos).
Uso: python herramientas/cohesion.py
"""
import ast
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parents[1] / "src" / "juegocartas"


def lcom4(clase: ast.ClassDef):
    metodos = [n for n in clase.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
               and not any(isinstance(d, ast.Name) and d.id in ("staticmethod", "classmethod") for d in n.decorator_list)]
    metodos = [m for m in metodos if m.args.args and m.args.args[0].arg == "self"]
    if len(metodos) < 2:
        return None
    nombres = {m.name for m in metodos}
    usa = {}
    for m in metodos:
        attrs, llamadas = set(), set()
        for n in ast.walk(m):
            if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and n.value.id == "self":
                (llamadas if n.attr in nombres else attrs).add(n.attr)
        usa[m.name] = (attrs, llamadas)
    padre = {n: n for n in nombres}

    def raiz(x):
        while padre[x] != x:
            x = padre[x]
        return x
    lista = list(nombres)
    for i, a in enumerate(lista):
        for b in lista[i + 1:]:
            if usa[a][0] & usa[b][0] or b in usa[a][1] or a in usa[b][1]:
                padre[raiz(a)] = raiz(b)
    return len({raiz(n) for n in nombres}), len(metodos)


filas = []
for archivo in sorted(RAIZ.rglob("*.py")):
    for nodo in ast.walk(ast.parse(archivo.read_text(encoding="utf8"))):
        if isinstance(nodo, ast.ClassDef):
            r = lcom4(nodo)
            if r:
                filas.append((str(archivo.relative_to(RAIZ)).replace("\\", "/"), nodo.name, *r))
print("| Archivo | Clase | Métodos | LCOM4 |\n|---|---|---|---|")
for f in filas:
    print(f"| {f[0]} | {f[1]} | {f[3]} | {f[2]} |")
altas = [f for f in filas if f[2] > 1]
print(f"\n{len(filas)} clases medidas; {len(filas) - len(altas)} con LCOM4 = 1; {len(altas)} con LCOM4 > 1.")
sys.exit(0)
