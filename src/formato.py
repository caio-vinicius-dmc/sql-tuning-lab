"""Número na convenção brasileira, para o que aparece na tela e no relatório.

O tempo medido continua sendo float o caminho inteiro. A vírgula entra só
na hora de escrever, e num lugar só, para a tela e o arquivo `.md` nunca
divergirem um do outro.
"""

from __future__ import annotations


def num(valor: float, casas: int = 1) -> str:
    """Formata com vírgula decimal.

    >>> num(9.19, 2)
    '9,19'
    >>> num(453.4)
    '453,4'
    """
    return f"{valor:.{casas}f}".replace(".", ",")


def milhar(valor: int) -> str:
    """Inteiro com ponto no milhar.

    >>> milhar(300000)
    '300.000'
    """
    return f"{valor:,}".replace(",", ".")
