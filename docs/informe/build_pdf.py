"""Construye Entregable3.pdf a partir de Entregable3.html con el estilo de la plantilla de portada UN.

Mismo proceso que el Entregable 1:
1. Toma los títulos h1/h2 y genera la página CONTENIDO.
2. Imprime con Chrome headless y recalcula los números de página del índice hasta que sean estables.
3. Estampa el sello de la UN en el encabezado de todas las páginas excepto la portada.

Uso: python build_pdf.py   (requiere PyMuPDF y Google Chrome)
"""
import html
import pathlib
import re
import subprocess

import fitz  # PyMuPDF

BASE = pathlib.Path(__file__).resolve().parent
SRC = BASE / "Entregable3.html"
TMP_HTML = BASE / "build" / "_build.html"
TMP_PDF = BASE / "build" / "_raw.pdf"
OUT = BASE / "Entregable3.pdf"
SELLO = BASE / "build" / "sello_un.png"
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
PT = 72  # puntos por pulgada
A4_ANCHO = 595.3


def headings(src):
    """Devuelve (cabecera, cuerpo_con_ids, [(nivel, id, texto)]) para los h1/h2 posteriores a la marca del índice."""
    head, body = src.split("<!--TOC-->", 1)
    items = []

    def add_id(m):
        lvl, attrs, inner = m.group(1), m.group(2), m.group(3)
        hid = f"sec{len(items) + 1}"
        text = html.unescape(re.sub(r"<[^>]+>", "", inner)).strip()
        items.append((int(lvl), hid, text))
        return f'<h{lvl}{attrs} id="{hid}">{inner}</h{lvl}>'

    body = re.sub(r"<h([12])([^>]*)>(.*?)</h\1>", add_id, body, flags=re.S)
    return head, body, items


def toc_html(items, pages):
    rows = []
    for (lvl, hid, text), pg in zip(items, pages):
        cls = "l1" if lvl == 1 else "l2"
        weight = ' style="font-weight:bold"' if lvl == 1 else ""
        rows.append(f'<a class="{cls}" href="#{hid}"{weight}><span class="t">{html.escape(text)}</span>'
                    f'<span class="d"></span><span class="n">{pg}</span></a>')
    return '<div class="toc"><h1>CONTENIDO</h1>\n' + "\n".join(rows) + "\n</div>\n"


def print_pdf(html_path, pdf_path):
    subprocess.run([CHROME, "--headless", "--disable-gpu", "--no-pdf-header-footer", "--allow-file-access-from-files",
                    "--virtual-time-budget=10000", f"--print-to-pdf={pdf_path}", html_path.as_uri()],
                   check=True, capture_output=True)


def find_pages(pdf_path, items, toc_pages):
    doc = fitz.open(pdf_path)
    norm = lambda t: re.sub(r"\s+", " ", t).strip()
    texts = [norm(p.get_text()) for p in doc]
    pages, start = [], toc_pages
    for _, _, text in items:
        key = norm(text)[:40]
        for i in range(start, len(texts)):
            if key in texts[i]:
                pages.append(i + 1)
                start = i
                break
        else:
            pages.append("?")
    return pages, len(doc)


def stamp(pdf_in, pdf_out):
    doc = fitz.open(pdf_in)
    for i, page in enumerate(doc):
        if i == 0:
            continue  # la portada no lleva encabezado
        w = page.rect.width
        if abs(w - A4_ANCHO) < 2:  # A4 vertical: centrado sobre el área de texto (márgenes 1in / 0.68in)
            cx = 1.0 * PT + (w - 1.0 * PT - 0.68 * PT) / 2
        else:
            cx = w / 2
        size = 0.75 * PT
        page.insert_image(fitz.Rect(cx - size / 2, 0.14 * PT, cx + size / 2, 0.14 * PT + size), filename=str(SELLO))
    doc.set_metadata({"title": "Entregable 2 - Arquitectura Detallada, Información, Riesgo y Gobernanza",
                      "author": "Catalina Arango Sierra, Elizabeth Alzate Zapata, Nicolas Meza Ortega",
                      "subject": "Fundamentos de Arquitectura de Software 2026-2 - Universidad Nacional de Colombia",
                      "creator": "", "producer": ""})
    doc.save(pdf_out, garbage=3, deflate=True)


def main():
    src = SRC.read_text(encoding="utf8")
    head, body, items = headings(src)
    pages = ["0"] * len(items)
    total = 0
    for _ in range(4):
        built = (head + toc_html(items, pages) + body).replace('src="build/', 'src="')
        TMP_HTML.write_text(built, encoding="utf8")
        print_pdf(TMP_HTML, TMP_PDF)
        new_pages, total = find_pages(TMP_PDF, items, toc_pages=2)
        if new_pages == pages:
            break
        pages = new_pages
    stamp(TMP_PDF, OUT)
    print(f"{OUT.name}: {total} páginas")
    for (lvl, _, text), pg in zip(items, pages):
        print(("  " if lvl == 2 else "") + f"{text[:70]} ... {pg}")


if __name__ == "__main__":
    main()
