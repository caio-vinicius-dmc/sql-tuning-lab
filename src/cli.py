"""Interface de linha de comando do laboratório.

    python -m src.cli preparar
    python -m src.cli listar
    python -m src.cli executar
    python -m src.cli executar --cenario 03 --cenario 06 --repeticoes 9
"""

from __future__ import annotations

import argparse
import sys

from rich.console import Console
from rich.table import Table

from . import banco, cenarios, config, relatorio
from .benchmark import executar_cenario
from .formato import num as _num

console = Console()


def comando_preparar(args: argparse.Namespace) -> int:
    cfg = config.carregar()
    console.print(f"Conectando em [bold]{cfg.resumo_conexao()}[/bold]...")
    banco.esperar_banco(cfg)

    console.print("Criando as tabelas...")
    banco.criar_schema(cfg)

    console.print(
        f"Gerando a massa ({cfg.qtd_pedidos:,} pedidos). "
        "Isso leva alguns segundos.".replace(",", ".")
    )
    segundos = banco.carregar_dados(cfg)

    console.print("Rodando VACUUM ANALYZE...")
    banco.vacuum_analyze(cfg)

    tabela = Table(title=f"Massa carregada em {_num(segundos)}s")
    tabela.add_column("Tabela")
    tabela.add_column("Linhas", justify="right")
    for nome, qtd in banco.contar_linhas(cfg).items():
        tabela.add_row(nome, f"{qtd:,}".replace(",", "."))
    console.print(tabela)

    console.print("\nPronto. Agora rode: [bold]python -m src.cli executar[/bold]")
    return 0


def comando_listar(args: argparse.Namespace) -> int:
    tabela = Table(title="Cenários disponíveis")
    tabela.add_column("#", style="bold")
    tabela.add_column("Cenário")
    tabela.add_column("O que demonstra")

    for c in cenarios.carregar_todos():
        tabela.add_row(c.codigo, c.titulo, c.espera)

    console.print(tabela)
    return 0


def comando_executar(args: argparse.Namespace) -> int:
    cfg = config.carregar()
    banco.esperar_banco(cfg)

    linhas = banco.contar_linhas(cfg)
    if linhas["pedidos"] == 0:
        console.print(
            "[red]As tabelas estão vazias.[/red] "
            "Rode [bold]python -m src.cli preparar[/bold] antes."
        )
        return 1

    escolhidos = cenarios.filtrar(cenarios.carregar_todos(), args.cenario)
    resultados = []

    for c in escolhidos:
        console.print(f"[bold]{c.codigo}[/bold] {c.titulo}... ", end="")
        resultado = executar_cenario(cfg, c, repeticoes=args.repeticoes)
        resultados.append(resultado)
        console.print(
            f"{_num(resultado.antes.mediana_ms)} ms -> "
            f"{_num(resultado.depois.mediana_ms)} ms "
            f"([green]{_num(resultado.fator)}x[/green])"
        )

    destino = relatorio.salvar(relatorio.montar(resultados, cfg, linhas))
    console.print(f"\nRelatório gravado em [bold]{destino.relative_to(config.RAIZ)}[/bold]")
    return 0


def construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sql-tuning-lab",
        description="Laboratório de otimizacao de consultas no PostgreSQL.",
    )
    sub = parser.add_subparsers(dest="comando", required=True)

    p_preparar = sub.add_parser("preparar", help="cria o schema e gera a massa de dados")
    p_preparar.set_defaults(funcao=comando_preparar)

    p_listar = sub.add_parser("listar", help="mostra os cenários cadastrados")
    p_listar.set_defaults(funcao=comando_listar)

    p_executar = sub.add_parser("executar", help="roda o benchmark e gera o relatório")
    p_executar.add_argument(
        "--cenario",
        action="append",
        metavar="CODIGO",
        help="roda apenas o cenário informado; pode repetir a opção",
    )
    p_executar.add_argument(
        "--repeticoes",
        type=int,
        default=5,
        help="quantas vezes medir cada consulta (padrão: 5)",
    )
    p_executar.set_defaults(funcao=comando_executar)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = construir_parser().parse_args(argv)
    try:
        return args.funcao(args)
    except RuntimeError as erro:
        console.print(f"[red]{erro}[/red]")
        return 1


if __name__ == "__main__":
    sys.exit(main())
