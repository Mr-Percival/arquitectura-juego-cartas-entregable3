"""Graba videos de demostración del MVP en el navegador (material para la exposición).

Dos navegadores juegan una ronda de cada modalidad contra un servidor local, a ritmo de persona
(pausas de 1 a 3 s), y se graba la pantalla del celular de quien muestra el juego.
Uso, desde `juego`:  python herramientas/video_demo.py   (Python con Playwright; el servidor usa el .venv)
"""
from __future__ import annotations

import pathlib
import random
import shutil
import socket
import subprocess
import sys
import time

from playwright.sync_api import sync_playwright

RAIZ = pathlib.Path(__file__).resolve().parents[1]
SALIDA = RAIZ / "docs" / "demo"
PUERTO = 8079
URL = f"http://127.0.0.1:{PUERTO}/"
VISTA = {"width": 412, "height": 892}
azar = random.Random(26)

# Política sencilla, la misma para los dos jugadores: lee la vista que manda el servidor (la pantalla no aplica reglas).
DECIDIR = """() => {
  const P = V.partida, A = P.analisis;
  const enCombo = A.combos.flatMap(c => c.cartas);
  const sueltas = mano.slice(); enCombo.forEach(c => { const i = sueltas.indexOf(c); if (i >= 0) sueltas.splice(i, 1); });
  const pts = c => c === "JK" ? -1 : Math.min(10, orden(c) === 1 ? 10 : orden(c));
  const pozoSirve = P.pozo && P.pozo !== "JK" && mano.filter(c => rango(c) === rango(P.pozo)).length >= 2;
  const descarte = sueltas.length ? sueltas.reduce((a, b) => pts(b) > pts(a) ? b : a) : mano[mano.length - 1];
  return { turno: P.en_turno, fase: P.fase, yo: V.yo, ganador: P.ganador, resumen: !!P.resumen,
           puede: A.puede_cerrar, pozoSirve, descarte, i: mano.indexOf(descarte) };
}"""


def pausa(a=1.0, b=2.6):
    time.sleep(azar.uniform(a, b))


def esperar_servidor():
    for _ in range(60):
        try:
            socket.create_connection(("127.0.0.1", PUERTO), 1).close()
            return
        except OSError:
            time.sleep(0.5)
    raise RuntimeError("El servidor no arrancó")


def cerrar_dialogos(pagina):
    for boton in ("#res-boton", "#reglas-ok"):
        b = pagina.locator(boton)
        if b.is_visible():
            b.click()


def jugar_turno(pagina, mostrar_error: bool) -> bool:
    """Juega el turno de esta página si le toca. Devuelve True si la ronda terminó."""
    d = pagina.evaluate(DECIDIR)
    if d["ganador"] or d["resumen"]:
        return True
    if d["turno"] != d["yo"]:
        return False
    if d["fase"] == "ESPERANDO_ROBO":
        pausa()
        pagina.click("#pozo" if d["pozoSirve"] else "#mazo")
        pausa(0.8, 1.6)
        return False
    if d["puede"]:
        pausa(1.5, 2.5)
        pagina.click("#cerrar")
        time.sleep(1.5)
        return True
    if mostrar_error:  # una vez por video: muestra el mensaje de la regla al intentar cerrar sin poder
        pausa(1.0, 1.8)
        pagina.click("#cerrar", force=True)
        time.sleep(3.0)
    pagina.click(f'#mano .carta[data-i="{d["i"]}"]')
    pausa(0.9, 1.8)
    pagina.click("#descartar")
    pausa(0.6, 1.2)
    return False


def grabar(navegador, variante: str, nombre: str, max_turnos: int = 70) -> pathlib.Path:
    tmp = SALIDA / "_tmp"
    ctx_a = navegador.new_context(viewport=VISTA, device_scale_factor=2, record_video_dir=str(tmp),
                                  record_video_size=VISTA, is_mobile=True, has_touch=True)
    ctx_b = navegador.new_context(viewport=VISTA, is_mobile=True, has_touch=True)
    a, b = ctx_a.new_page(), ctx_b.new_page()
    a.goto(URL); b.goto(URL)
    time.sleep(1.5)
    a.fill("#nombre", "Nicolas"); pausa(0.5, 1)
    a.click(f'.modo[data-variante="{variante}"]'); pausa()
    a.click("#crear-sala")
    a.wait_for_selector("#codigo-sala:not(:empty)")
    codigo = a.inner_text("#codigo-sala")
    b.fill("#nombre", "Catalina"); b.fill("#codigo-unirse", codigo); b.click("#unirse")
    pausa(1.5, 2.5)
    a.click("#ayuda-sala"); time.sleep(4.5); a.click("#reglas-ok"); pausa()
    a.click("#empezar")
    a.wait_for_selector("#vista-juego:not([hidden])"); b.wait_for_selector("#vista-juego:not([hidden])")
    pausa(2, 3)
    error_mostrado = False
    for _ in range(max_turnos * 2):
        terminado = False
        for pagina in (a, b):
            mostrar = pagina is a and not error_mostrado and pagina.evaluate("V.partida.fase") == "ESPERANDO_DESCARTE" \
                and pagina.evaluate("V.partida.en_turno === V.yo && !V.partida.analisis.puede_cerrar")
            terminado = jugar_turno(pagina, mostrar) or terminado
            error_mostrado = error_mostrado or mostrar
            time.sleep(0.3)
        if terminado:
            break
    time.sleep(6)  # que se lea el resumen de la ronda
    video = a.video
    ctx_a.close(); ctx_b.close()
    destino = SALIDA / f"{nombre}.webm"
    shutil.move(video.path(), destino)
    return destino


def main():
    SALIDA.mkdir(parents=True, exist_ok=True)
    servidor = subprocess.Popen([str(RAIZ / ".venv" / "Scripts" / "python"), "-m", "uvicorn", "juegocartas.arranque:app",
                                 "--port", str(PUERTO)], cwd=RAIZ, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        esperar_servidor()
        with sync_playwright() as p:
            try:
                nav = p.chromium.launch()
            except Exception:
                nav = p.chromium.launch(executable_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe")
            for variante, nombre in (("CLASICA_433", "demo_clasica"), ("APUNTADO_101", "demo_apuntado")):
                print(grabar(nav, variante, nombre))
            nav.close()
    finally:
        servidor.terminate()
        shutil.rmtree(SALIDA / "_tmp", ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
