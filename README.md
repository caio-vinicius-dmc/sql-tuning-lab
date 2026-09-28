# sql-tuning-lab

Um laboratório para ver, na prática, o que acontece quando você cria o
índice certo num banco de dados PostgreSQL.

## Do que se trata, em linguagem simples

Banco de dados guarda informação em tabelas, como uma planilha gigante.
Quando você pede uma informação específica — "me mostre os pedidos da
semana passada" — o banco precisa encontrá-la. Sem ajuda, ele lê a tabela
inteira, linha por linha, e joga fora tudo que não serve.

Um **índice** é o atalho. Funciona como o índice remissivo no fim de um
livro: em vez de folhear as 400 páginas procurando uma palavra, você
consulta a lista alfabética e vai direto na página certa.

Este projeto monta uma base com 300 mil pedidos e 750 mil itens, roda sete
consultas lentas de verdade, cria o índice certo para cada uma e mede a
diferença. Tudo automático: você dá dois comandos e recebe um relatório.

A ideia nasceu de uma frustração comum. Quase todo material sobre índices
explica a teoria com uma tabela de dez linhas — e com dez linhas o banco
lê tudo de qualquer jeito, então nada do que foi dito aparece no
resultado. Aqui o volume é grande o suficiente para a diferença ser real.

## O que você vai ver

Estes são os números de uma execução de verdade, numa máquina comum:

| # | O problema | Antes | Depois | Ficou |
|---|-----------|-------|--------|-------|
| 01 | Filtrar por data sem índice | 9,57 ms | 1,12 ms | 8,5x mais rápido |
| 02 | Cruzar duas tabelas com filtro dos dois lados | 12,02 ms | 5,88 ms | 2,0x |
| 03 | Procurar um valor raro numa coluna | 12,14 ms | 0,11 ms | 114,5x |
| 04 | Ordenar tudo só para mostrar 20 linhas | 27,82 ms | 0,06 ms | 488,0x |
| 05 | Usar uma função na coluna filtrada | 4,37 ms | 0,04 ms | 109,3x |
| 06 | Ler a tabela quando o índice já tinha a resposta | 20,82 ms | 3,63 ms | 5,7x |
| 07 | Consulta escrita de um jeito que impede o índice | 15,48 ms | 0,39 ms | 40,0x |

O relatório completo, com o passo a passo que o banco seguiu em cada caso,
está em [docs/exemplo-relatorio.md](docs/exemplo-relatorio.md).

Uma observação honesta sobre esses números: os ganhos de três dígitos são
grandes porque a consulta devolve poucas linhas, e aí praticamente todo o
tempo era a varredura desnecessária. O caso 02, com 2x, é o mais parecido
com o que se encontra no dia a dia.

Os tempos variam de uma máquina para outra e entre execuções. O que se
repete é a mudança no caminho que o banco escolhe, que é o que a última
coluna do relatório mostra.

## O que você precisa ter instalado

- **Docker Desktop** — programa que sobe o banco de dados para você, sem
  instalar nada permanente na máquina. Baixe em
  [docker.com](https://www.docker.com/products/docker-desktop/) e deixe
  aberto.
- **Python 3.11 ou mais novo** — baixe em
  [python.org](https://www.python.org/downloads/). Na instalação, marque a
  opção "Add Python to PATH".

## Como rodar

Abra o terminal na pasta do projeto e siga os cinco passos.

**1. Crie o arquivo de configuração.** Ele guarda a senha do banco local.

```bash
cp .env.example .env
```

No Windows, se o `cp` não funcionar, use `copy .env.example .env`.

**2. Suba o banco de dados.**

```bash
docker compose up -d
```

Na primeira vez o Docker baixa o PostgreSQL, o que leva um ou dois
minutos. Depois é instantâneo.

**3. Prepare o ambiente do Python.**

```bash
python -m venv .venv
.venv/Scripts/activate
pip install -r requirements.txt
```

No Linux ou macOS, a segunda linha é `source .venv/bin/activate`.

O `venv` é uma pasta isolada para as bibliotecas deste projeto, para elas
não se misturarem com as de outros. Quando funciona, o nome `(.venv)`
aparece no começo da linha do terminal.

**4. Gere os dados.** Leva cerca de 30 segundos.

```bash
python -m src.cli preparar
```

Você deve ver a contagem das tabelas criadas: 20 mil clientes, 2 mil
produtos, 300 mil pedidos e 750 mil itens.

**5. Rode a medição.**

```bash
python -m src.cli executar
```

Cada cenário aparece na tela com o antes, o depois e quantas vezes ficou
mais rápido. No fim, o relatório completo é gravado na pasta
`relatorios/`, com a data e a hora no nome do arquivo.

### Quando terminar

Para desligar o banco e apagar os dados:

```bash
docker compose down -v
```

## Outros comandos

```bash
python -m src.cli listar                     # o que cada cenário demonstra
python -m src.cli executar --cenario 03      # roda só um deles
python -m src.cli executar --repeticoes 15   # mede mais vezes, resultado mais estável
```

## Como a medição é feita

Cada consulta roda uma vez para "aquecer" — essa primeira é descartada — e
mais cinco vezes valendo. O número que aparece é a **mediana**, não a
média. A mediana ignora melhor um pico isolado: se o antivírus acordar no
meio do teste, a média sobe e a mediana não.

Os índices são criados e apagados dentro de cada cenário. Isso significa
que a ordem não importa: rodar só o cenário 06 dá o mesmo resultado que
rodá-lo depois dos outros seis.

Os detalhes estão em [docs/metodologia.md](docs/metodologia.md).

## Estrutura das pastas

```
cenarios.toml            a lista dos cenários: título, problema e solução
sql/schema.sql           as tabelas, sem nenhum índice além das chaves
sql/dados.sql            a geração dos dados de mentira
sql/cenarios/NN_nome/    a consulta e o índice de cada cenário
src/                     o código que carrega, mede e escreve o relatório
docs/                    a metodologia e um relatório de verdade
relatorios/              onde os seus relatórios são gravados
```

## Criando um cenário novo

1. Crie a pasta `sql/cenarios/08_seu_cenario/` com dois arquivos:
   `consulta.sql` (a consulta lenta) e `indice.sql` (o índice que resolve).
2. Se a solução for reescrever a consulta em vez de criar índice, adicione
   também `consulta_otimizada.sql`. Se o cenário precisar de um índice que
   já exista antes da medição, use `indice_previo.sql`.
3. Acrescente o bloco correspondente no arquivo `cenarios.toml`.

Nenhuma linha de Python precisa mudar.

## Problemas comuns

**"ports are not available" ou "bind: An attempt was made to access a socket
in a way forbidden by its access permissions".** O Windows reserva faixas de
porta para uso próprio, e elas mudam a cada reinício. Veja quais estão
reservadas com:

```bash
netsh int ipv4 show excludedportrange protocol=tcp
```

Se a porta do projeto estiver numa das faixas, mude `POSTGRES_PORT` no
arquivo `.env` para qualquer valor livre abaixo de 49152 e suba de novo.

**"O banco recusou a senha."** Você mudou a senha no arquivo `.env` depois
de já ter subido o banco. O PostgreSQL só lê a senha na primeira vez que
cria os dados e ignora mudanças depois disso. Resolva apagando e
recriando:

```bash
docker compose down -v && docker compose up -d
```

**"Não consegui conectar."** O Docker Desktop provavelmente não está
aberto. Abra, espere o ícone parar de animar e tente de novo.

**O comando `python` não é reconhecido.** O Python não foi adicionado ao
PATH na instalação. Reinstale marcando essa opção, ou tente `py` no lugar
de `python`.

## Limitações

- O banco roda com configuração fixa, definida no `docker-compose.yml`,
  para a comparação ser estável entre máquinas diferentes. Não é um ajuste
  de servidor.
- Os dados cabem na memória depois do primeiro acesso. O ganho medido aqui
  vem de ler menos, não de evitar o disco. Em bases que não cabem na
  memória, a diferença tende a ser maior, não menor.
- Os sete cenários cobrem índices do tipo B-tree, que é o mais comum.
  Outros tipos (GIN, GiST, BRIN), que resolvem problemas diferentes,
  ficaram de fora.
- Os tempos absolutos dependem da máquina. O que deve se repetir em
  qualquer ambiente é a mudança no caminho que o banco escolhe.

---

## 👤 Autor

Desenvolvido por **Caio Vinícius Barbosa Barros**.

Se você tiver dúvidas, sugestões ou quiser reportar um problema, sinta-se à vontade para entrar em contato:

*   **✉️ E-mail:** [caio@dynamicmotioncentury.com.br](mailto:caio@dynamicmotioncentury.com.br)
*   **🌐 Site/Portfólio:** [www.dynamicmotioncentury.com.br](https://dynamicmotioncentury.com.br)
*   **💼 LinkedIn:** [linkedin.com/in/caio-vinicius-dmc](https://linkedin.com/in/caio-vinicius-dmc)
*   **🐙 GitHub:** [@caio-vinicius-dmc](https://github.com/caio-vinicius-dmc)

💡 *Se este projeto te ajudou, deixe uma ⭐ no repositório!*
