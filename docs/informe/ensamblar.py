"""Une estilo + cuerpo + fragmentos de cada sección en Entregable3.html y numera las figuras."""
import pathlib, re
B = pathlib.Path(__file__).resolve().parent
css = (B / "build" / "_estilo.css.txt").read_text(encoding="utf8")
cuerpo = (B / "cuerpo.html").read_text(encoding="utf8")
for n in (1, 3, 4):
    cuerpo = cuerpo.replace(f"<!--FRAG{n}-->", (B / f"frag_{n}.html").read_text(encoding="utf8"))
k = iter(range(1, 100))
cuerpo = re.sub(r"Figura X", lambda m: f"Figura {next(k)}", cuerpo)
html = ('<!doctype html>\n<html lang="es">\n<head>\n<meta charset="utf-8">\n'
        '<title>Entregable 3 - MVP, Validación y Retrospectiva</title>\n' + css + '\n</head>\n<body>\n' + cuerpo + '\n</body>\n</html>\n')
(B / "Entregable3.html").write_text(html, encoding="utf8")
print("ok", html.count("Figura "))
