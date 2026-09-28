"""Leitura da configuração do laboratório a partir de variáveis de ambiente."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parent.parent

# O .env fica fora do controle de versão. Se não existir, os defaults abaixo
# batem com o docker-compose.yml e o laboratório sobe assim mesmo.
load_dotenv(RAIZ / ".env")


@dataclass(frozen=True)
class Config:
    host: str
    porta: int
    banco: str
    usuario: str
    senha: str
    qtd_clientes: int
    qtd_produtos: int
    qtd_pedidos: int

    @property
    def dsn(self) -> str:
        return (
            f"host={self.host} port={self.porta} dbname={self.banco} "
            f"user={self.usuario} password={self.senha}"
        )

    def resumo_conexao(self) -> str:
        """Mesma informação do DSN, mas sem a senha -- seguro para log."""
        return f"{self.usuario}@{self.host}:{self.porta}/{self.banco}"


def carregar() -> Config:
    return Config(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        porta=int(os.getenv("POSTGRES_PORT", "15432")),
        banco=os.getenv("POSTGRES_DB", "tuning_lab"),
        usuario=os.getenv("POSTGRES_USER", "tuning"),
        senha=os.getenv("POSTGRES_PASSWORD", "tuning_local"),
        qtd_clientes=int(os.getenv("QTD_CLIENTES", "20000")),
        qtd_produtos=int(os.getenv("QTD_PRODUTOS", "2000")),
        qtd_pedidos=int(os.getenv("QTD_PEDIDOS", "300000")),
    )
