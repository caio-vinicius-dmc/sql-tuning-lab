"""Geração do relatório em Markdown a partir dos resultados do benchmark."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from .benchmark import Medicao, Resultado
from .config import RAIZ, Config
from .formato import milhar, num as _num

PASTA_RELATORIOS = RAIZ / "relatorios"



def _linha_resumo(r: Resultado) -> str:
    return (
        f"| {r.cenario.codigo} "
        f"| {r.cenario.titulo} "
        f"| {_num(r.antes.mediana_ms, 2)} ms "
        f"| {_num(r.depois.mediana_ms, 2)} ms "
        f"| {_num(r.fator)}x "
        f"| {r.antes.nos_de_leitura} -> {r.depois.nos_de_leitura} |"
    )


def _bloco_medicao(rotulo: str, m: Medicao) -> str:
    return (
        f"**{rotulo}** -- mediana {_num(m.mediana_ms, 2)} ms "
        f"(melhor {_num(m.melhor_ms, 2)} ms), "
        f"{m.blocos_lidos + m.blocos_cache} blocos tocados "
        f"({m.blocos_lidos} de disco, {m.blocos_cache} de cache), "
        f"{m.linhas_devolvidas} linhas.\n\n"
        "```\n"
        f"{m.plano_texto}\n"
        "```\n"
    )


def montar(resultados: list[Resultado], cfg: Config, linhas: dict[str, int]) -> str:
    agora = datetime.now().strftime("%d/%m/%Y às %H:%M")
    volume = ", ".join(f"{t}: {milhar(q)}" for t, q in linhas.items())

    partes = [
        "# Relatório de tuning",
        "",
        f"Execução de {agora}. Banco `{cfg.banco}` no PostgreSQL local.",
        f"Volume da massa: {volume}.",
        "",
        "Cada cenário foi medido com `EXPLAIN (ANALYZE, BUFFERS)`, descartando a",
        "primeira execução e tomando a mediana das seguintes. Os índices são",
        "criados e removidos dentro do próprio cenário, então a ordem de execução",
        "não influencia o resultado.",
        "",
        "## Resumo",
        "",
        "| # | Cenário | Antes | Depois | Ganho | Plano |",
        "|---|---------|-------|--------|-------|-------|",
    ]
    partes.extend(_linha_resumo(r) for r in resultados)
    partes.append("")

    for r in resultados:
        c = r.cenario
        partes.extend(
            [
                f"## {c.codigo} - {c.titulo}",
                "",
                f"**Problema.** {c.problema}",
                "",
                f"**Correção.** {c.solucao}",
                "",
                "### Consulta",
                "",
                "```sql",
                c.consulta,
                "```",
                "",
            ]
        )

        if c.houve_reescrita:
            partes.extend(
                ["### Consulta reescrita", "", "```sql", c.consulta_depois, "```", ""]
            )

        if c.ddl_indices:
            partes.extend(["### Índice criado", "", "```sql", c.ddl_indices, "```", ""])

        partes.extend(
            [
                "### Antes",
                "",
                _bloco_medicao("Sem a correção", r.antes),
                "### Depois",
                "",
                _bloco_medicao("Com a correção", r.depois),
                f"Resultado: {_num(r.fator)}x mais rápido "
                f"({_num(r.ganho_percentual)}% de redução no tempo de execução).",
                "",
            ]
        )

    return "\n".join(partes)


def salvar(conteudo: str) -> Path:
    PASTA_RELATORIOS.mkdir(exist_ok=True)
    destino = PASTA_RELATORIOS / f"{datetime.now():%Y-%m-%d_%H%M%S}.md"
    destino.write_text(conteudo, encoding="utf-8")
    return destino
