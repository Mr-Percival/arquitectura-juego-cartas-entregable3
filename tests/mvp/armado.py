"""Fixtures del MVP (mismo cableado que juegocartas.arranque, sin servidor).

No se llama conftest.py porque las fitness functions importan su propio `conftest` por nombre.
"""
import pytest

from juegocartas.arranque import armar_gateway


@pytest.fixture
def gateway():
    return armar_gateway()


@pytest.fixture
def juego(gateway):
    return gateway._juego
