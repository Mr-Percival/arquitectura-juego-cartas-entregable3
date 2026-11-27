"""Plan de reversa: si la base no responde (caída o vencida), el juego arranca en memoria en vez de caerse."""
from juegocartas.arranque import repositorio_del_entorno
from juegocartas.persistencia.memoria import RepositorioEnMemoria


def test_sin_database_url_usa_memoria(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert isinstance(repositorio_del_entorno(), RepositorioEnMemoria)


def test_base_inalcanzable_arranca_en_memoria(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://nadie:nada@base-que-no-existe.invalid:5432/juego?connect_timeout=2")
    assert isinstance(repositorio_del_entorno(), RepositorioEnMemoria)
