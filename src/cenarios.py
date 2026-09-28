"""Carrega a definição dos cenários a partir do cenarios.toml + pasta sql/."""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

from .config import RAIZ

PASTA_CENARIOS = RAIZ / "sql" / "cenarios"

# Usado para descobrir o nome dos índices criados pelo cenário e conseguir
# remove-los no início da próxima execução.
PADRAO_NOME_INDICE = re.compile(
    r"CREATE\s+(?:UNIQUE\s+)?INDEX\s+(?:CONCURRENTLY\s+)?(?:IF\s+NOT\s+EXISTS\s+)?(\w+)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Cenario:
    codigo: str
    nome: str
    titulo: str
    problema: str
    solucao: str
    espera: str
    consulta: str
    consulta_otimizada: str | None
    ddl_indices: str | None
    ddl_indices_previos: str | None

    @property
    def identificador(self) -> str:
        return f"{self.codigo}_{self.nome}"

    @property
    def consulta_depois(self) -> str:
        """A consulta medida na fase 'depois'.

        Na maioria dos cenários é a mesma de antes: o que mudou foi o banco.
        No cenário de reescrita e o contrário -- o banco é o mesmo e a
        consulta e que foi corrigida.
        """
        return self.consulta_otimizada or self.consulta

    @property
    def houve_reescrita(self) -> bool:
        return self.consulta_otimizada is not None

    def nomes_dos_indices(self) -> list[str]:
        ddl = f"{self.ddl_indices_previos or ''}\n{self.ddl_indices or ''}"
        return PADRAO_NOME_INDICE.findall(ddl)


def _ler_opcional(caminho: Path) -> str | None:
    if not caminho.exists():
        return None
    conteudo = caminho.read_text(encoding="utf-8").strip()
    # Arquivos que só tem comentário contam como "nenhum comando".
    sem_comentarios = "\n".join(
        linha for linha in conteudo.splitlines() if not linha.strip().startswith("--")
    ).strip()
    return conteudo if sem_comentarios else None


def carregar_todos() -> list[Cenario]:
    definicoes = tomllib.loads((RAIZ / "cenarios.toml").read_text(encoding="utf-8"))
    cenarios: list[Cenario] = []

    for item in definicoes["cenario"]:
        pasta = PASTA_CENARIOS / f"{item['codigo']}_{item['nome']}"
        if not pasta.is_dir():
            raise FileNotFoundError(
                f"O cenário {item['codigo']} está declarado no cenarios.toml "
                f"mas a pasta {pasta} não existe."
            )
        cenarios.append(
            Cenario(
                codigo=item["codigo"],
                nome=item["nome"],
                titulo=item["titulo"],
                problema=item["problema"],
                solucao=item["solucao"],
                espera=item["espera"],
                consulta=(pasta / "consulta.sql").read_text(encoding="utf-8").strip(),
                consulta_otimizada=_ler_opcional(pasta / "consulta_otimizada.sql"),
                ddl_indices=_ler_opcional(pasta / "indice.sql"),
                ddl_indices_previos=_ler_opcional(pasta / "indice_previo.sql"),
            )
        )

    return cenarios


def filtrar(cenarios: list[Cenario], codigos: list[str] | None) -> list[Cenario]:
    if not codigos:
        return cenarios
    escolhidos = [c for c in cenarios if c.codigo in codigos]
    if not escolhidos:
        disponiveis = ", ".join(c.codigo for c in cenarios)
        raise SystemExit(f"Nenhum cenário com esse código. Disponíveis: {disponiveis}")
    return escolhidos
