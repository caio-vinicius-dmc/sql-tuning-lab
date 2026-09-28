"""Conexão com o Postgres e preparação da massa de dados."""

from __future__ import annotations

import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import psycopg

from .config import RAIZ, Config


@contextmanager
def conectar(cfg: Config, autocommit: bool = False) -> Iterator[psycopg.Connection]:
    with psycopg.connect(cfg.dsn, autocommit=autocommit) as conn:
        yield conn


def esperar_banco(cfg: Config, tentativas: int = 30, intervalo: float = 2.0) -> None:
    """Aguarda o container aceitar conexões.

    O healthcheck do compose já cobre isso, mas quem roda o script logo depois
    do `docker compose up -d` costuma chegar antes do banco estar pronto.
    """
    ultimo_erro: Exception | None = None
    for _ in range(tentativas):
        try:
            with psycopg.connect(cfg.dsn, connect_timeout=3) as conn:
                conn.execute("SELECT 1")
            return
        except psycopg.OperationalError as erro:
            # Senha recusada não melhora com nova tentativa -- insistir só
            # faz o comando demorar um minuto para dar a mensagem errada.
            #
            # O caso clássico e o volume do Docker ter sido criado com outra
            # senha: o Postgres só lê POSTGRES_PASSWORD na primeira
            # inicialização do diretório de dados e ignora a mudança no .env
            # depois disso.
            if "password authentication failed" in str(erro):
                raise RuntimeError(
                    f"O banco recusou a senha de {cfg.resumo_conexao()}. "
                    "Se você mudou POSTGRES_PASSWORD depois de já ter subido o "
                    "container, o volume antigo ainda guarda a senha original. "
                    "Recrie o ambiente com: docker compose down -v && docker compose up -d"
                ) from erro

            ultimo_erro = erro
            time.sleep(intervalo)
    raise RuntimeError(
        f"Não consegui conectar em {cfg.resumo_conexao()}. "
        f"O container está de pé? Último erro: {ultimo_erro}"
    )


def ler_sql(caminho: Path) -> str:
    return caminho.read_text(encoding="utf-8")


def criar_schema(cfg: Config) -> None:
    with conectar(cfg) as conn:
        conn.execute(ler_sql(RAIZ / "sql" / "schema.sql"))


def carregar_dados(cfg: Config) -> float:
    """Popula as tabelas e devolve quanto tempo levou, em segundos."""
    sql = ler_sql(RAIZ / "sql" / "dados.sql").format(
        qtd_clientes=int(cfg.qtd_clientes),
        qtd_produtos=int(cfg.qtd_produtos),
        qtd_pedidos=int(cfg.qtd_pedidos),
    )
    inicio = time.perf_counter()
    with conectar(cfg) as conn:
        conn.execute(sql)
    return time.perf_counter() - inicio


def vacuum_analyze(cfg: Config) -> None:
    """VACUUM precisa rodar fora de transação, dai o autocommit.

    Sem ele o mapa de visibilidade fica desatualizado e o cenário de
    Index Only Scan nunca mostra ganho -- o plano até usa o índice, mas
    volta no heap para conferir visibilidade linha a linha.
    """
    with conectar(cfg, autocommit=True) as conn:
        conn.execute("VACUUM (ANALYZE) clientes, produtos, pedidos, itens_pedido")


def contar_linhas(cfg: Config) -> dict[str, int]:
    tabelas = ("clientes", "produtos", "pedidos", "itens_pedido")
    with conectar(cfg) as conn:
        return {
            tabela: conn.execute(f"SELECT count(*) FROM {tabela}").fetchone()[0]
            for tabela in tabelas
        }
