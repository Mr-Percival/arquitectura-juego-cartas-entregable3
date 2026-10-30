"""Servidor web: entrega la pantalla de juego, abre el WebSocket hacia el GameGateway y deja
descargar la bitácora de auditoría de una sala como CSV (H6, evidencia de la sección 3.2)."""
from __future__ import annotations

import csv
import io
from pathlib import Path

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, Response

from juegocartas.nucleo.sala.salas import ErrorSala

from .gateway import GameGateway

COLUMNAS = ("ocurrida_en", "partida", "ronda", "turno", "jugador", "accion", "carta", "resultado", "motivo")

PANTALLA = Path(__file__).parent / "static" / "index.html"


def crear_app(gateway: GameGateway) -> FastAPI:
    app = FastAPI(title="Juego de cartas")

    @app.get("/")
    def pantalla() -> FileResponse:
        return FileResponse(PANTALLA)

    @app.get("/salud")
    def salud() -> dict:
        return {"estado": "ok"}

    @app.get("/bitacora/{codigo}.csv")
    def bitacora(codigo: str) -> Response:
        try:
            filas = gateway.bitacora(codigo)
        except ErrorSala as exc:
            raise HTTPException(404, str(exc)) from exc
        salida = io.StringIO()
        escritor = csv.DictWriter(salida, COLUMNAS, extrasaction="ignore")
        escritor.writeheader()
        escritor.writerows({**f, "ocurrida_en": f["ocurrida_en"].isoformat(timespec="milliseconds")} for f in filas)
        return Response(salida.getvalue(), media_type="text/csv; charset=utf-8",
                        headers={"Content-Disposition": f'attachment; filename="bitacora-{codigo.upper()}.csv"'})

    @app.websocket("/ws")
    async def juego(websocket: WebSocket) -> None:
        await websocket.accept()
        sesion = None
        try:
            while True:
                mensaje = await websocket.receive_json()
                if isinstance(mensaje, dict):
                    sesion = await gateway.atender(websocket, sesion, mensaje)
        except WebSocketDisconnect:
            await gateway.desconectar(sesion, websocket)

    return app
