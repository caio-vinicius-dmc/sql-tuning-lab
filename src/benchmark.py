"""Medição das consultas: executa, coleta o plano e compara antes x depois."""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field

import psycopg

from .banco import conectar
from .cenarios import Cenario
from .config import Config


@dataclass
class Medicao:
    """Resultado de uma consulta medida varias vezes."""

    tempos_ms: list[float] = field(default_factory=list)
    plano_texto: str = ""
    nos_de_leitura: str = ""
    blocos_lidos: int = 0
    blocos_cache: int = 0
    linhas_devolvidas: int = 0

    @property
    def mediana_ms(self) -> float:
        return statistics.median(self.tempos_ms)

    @property
    def melhor_ms(self) -> float:
        return min(self.tempos_ms)


@dataclass
class Resultado:
    cenario: Cenario
    antes: Medicao
    depois: Medicao

    @property
    def ganho_percentual(self) -> float:
        base = self.antes.mediana_ms
        if base == 0:
            return 0.0
        return (base - self.depois.mediana_ms) / base * 100

    @property
    def fator(self) -> float:
        """Quantas vezes ficou mais rápido. 1.0 significa que não mudou."""
        if self.depois.mediana_ms == 0:
            return float("inf")
        return self.antes.mediana_ms / self.depois.mediana_ms


def _nos_de_leitura(no: dict, encontrados: list[str] | None = None) -> list[str]:
    """Lista os nos do plano que tocam uma tabela ou índice.

    O no raiz quase nunca e o interessante: numa agregação ele será sempre
    "Aggregate", antes e depois. Quem muda quando um índice entra em cena e
    o no de leitura lá embaixo da árvore.
    """
    if encontrados is None:
        encontrados = []
    if "Relation Name" in no and no["Node Type"] not in encontrados:
        encontrados.append(no["Node Type"])
    for filho in no.get("Plans", []):
        _nos_de_leitura(filho, encontrados)
    return encontrados


def _somar_blocos(no: dict) -> tuple[int, int]:
    """Percorre a árvore do plano somando os buffers de todos os nos."""
    lidos = no.get("Shared Read Blocks", 0)
    cache = no.get("Shared Hit Blocks", 0)
    for filho in no.get("Plans", []):
        sub_lidos, sub_cache = _somar_blocos(filho)
        lidos += sub_lidos
        cache += sub_cache
    return lidos, cache


def _executar_explain(conn: psycopg.Connection, consulta: str) -> dict:
    linha = conn.execute(
        f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) {consulta}"
    ).fetchone()[0]
    return linha[0]


def _plano_em_texto(conn: psycopg.Connection, consulta: str) -> str:
    linhas = conn.execute(f"EXPLAIN (ANALYZE, BUFFERS) {consulta}").fetchall()
    return "\n".join(linha[0] for linha in linhas)


def medir(
    conn: psycopg.Connection,
    consulta: str,
    repeticoes: int = 5,
    aquecimentos: int = 1,
) -> Medicao:
    """Roda a consulta N vezes e devolve a mediana dos tempos de execução.

    A primeira execução costuma pagar leitura de disco e carga de catálogo;
    por isso ela e descartada. A mediana (e não a média) evita que um pico
    isolado da máquina distorca a comparação.
    """
    medicao = Medicao()

    for _ in range(aquecimentos):
        _executar_explain(conn, consulta)

    for _ in range(repeticoes):
        plano = _executar_explain(conn, consulta)
        medicao.tempos_ms.append(plano["Execution Time"])

    # O último plano coletado serve de amostra para o relatório.
    raiz = plano["Plan"]
    medicao.nos_de_leitura = ", ".join(_nos_de_leitura(raiz)) or raiz["Node Type"]
    medicao.linhas_devolvidas = raiz.get("Actual Rows", 0)
    medicao.blocos_lidos, medicao.blocos_cache = _somar_blocos(raiz)
    medicao.plano_texto = _plano_em_texto(conn, consulta)

    return medicao


def _remover_indices(conn: psycopg.Connection, cenario: Cenario) -> None:
    for nome in cenario.nomes_dos_indices():
        conn.execute(f"DROP INDEX IF EXISTS {nome}")


def executar_cenario(
    cfg: Config, cenario: Cenario, repeticoes: int = 5
) -> Resultado:
    """Mede a consulta antes e depois da correção proposta pelo cenário.

    O estado do banco é sempre devolvido ao ponto de partida no final, para
    que os cenários possam rodar em qualquer ordem sem interferir entre si.
    """
    with conectar(cfg, autocommit=True) as conn:
        _remover_indices(conn, cenario)

        # Alguns cenários começam com um índice já criado, porque o problema
        # que eles demonstram não é a ausência de índice.
        if cenario.ddl_indices_previos:
            conn.execute(cenario.ddl_indices_previos)
            conn.execute("ANALYZE pedidos")

        antes = medir(conn, cenario.consulta, repeticoes)

        if cenario.ddl_indices:
            conn.execute(cenario.ddl_indices)
            # Índices de expressão só ganham estatísticas após o ANALYZE.
            conn.execute("ANALYZE clientes, produtos, pedidos, itens_pedido")

        depois = medir(conn, cenario.consulta_depois, repeticoes)

        _remover_indices(conn, cenario)

    return Resultado(cenario=cenario, antes=antes, depois=depois)
