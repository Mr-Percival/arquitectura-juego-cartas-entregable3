"""Servidor web: entrega la pantalla de juego y abre el WebSocket hacia el GameGateway."""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse

from .gateway import GameGateway

PANTALLA = Path(__file__).parent / "static" / "index.html"


def crear_app(gateway: GameGateway) -> FastAPI:
    app = FastAPI(title="Juego de cartas")

    @app.get("/")
    def pantalla() -> FileResponse:
        return FileResponse(PANTALLA)

    @app.get("/salud")
    def salud() -> dict:
        return {"estado": "ok"}

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
            gateway.desconectar(sesion, websocket)

    return app
