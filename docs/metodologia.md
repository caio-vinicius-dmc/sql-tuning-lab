# Como as medições são feitas

Anotações sobre as decisões do benchmark. A maioria delas existe porque a
primeira versão dava números que não se repetiam entre execuções.

## Mediana em vez de média

Cada consulta roda uma vez para aquecer e mais N vezes para valer. A primeira
execução paga leitura de disco, carga de catálogo e plano novo, então ela e
sempre descartada.

Das restantes, o relatório usa a mediana. Média e sensível demais a um único
pico: basta o antivirus acordar no meio do teste para o número subir 30% sem
que nada tenha mudado no banco.

## VACUUM ANALYZE na carga

Duas razões diferentes:

- **ANALYZE** atualiza as estatísticas. Sem elas o planejador estima errado a
  seletividade dos filtros e pode escolher Seq Scan mesmo com um índice bom
  disponível. A comparação antes/depois perderia o sentido.
- **VACUUM** atualiza o mapa de visibilidade. O cenário 06 depende disso: sem
  o mapa em dia o plano até escolhe Index Only Scan, mas precisa voltar ao
  heap para conferir a visibilidade de cada linha (`Heap Fetches` alto) e o
  ganho desaparece.

`VACUUM` não roda dentro de transação, por isso aquela conexão específica com
`autocommit=True` em `src/banco.py`.

## Índices criados e removidos por cenário

No começo o script criava todos os índices de uma vez. O problema e que o
cenário 04 ficava rápido "de graca" por causa do índice criado no 01, e o
número de antes deixava de ser honesto.

Hoje cada cenário derruba os próprios índices antes de começar, cria o que
precisa no meio da medição e derruba tudo no final. Rodar um cenário isolado
da o mesmo resultado que rodar a bateria inteira.

## Nos de leitura no lugar do no raiz

O resumo do relatório mostra os nos que tocam tabela ou índice, não o no raiz
do plano. Numa consulta com `GROUP BY` o topo da árvore será `Aggregate` antes
e depois, o que não informa nada. O que muda com o índice está na base:
`Seq Scan` virando `Index Scan`, `Bitmap Heap Scan` ou `Index Only Scan`.

## Seed fixo na geração de dados

`SELECT setseed(0.42)` no início do `dados.sql` garante que duas cargas
produzam exatamente a mesma massa. Sem isso, a proporção de pedidos
cancelados oscilava entre execuções e o ganho do cenário 03 variava junto.

Um detalhe que custou tempo: a quantidade de itens por pedido usava
`random()` dentro do `LATERAL`. O planejador avaliou a função volátil uma
única vez e todos os 300 mil pedidos sairam com quatro itens. Hoje o tamanho
do pedido vem de `p.id % 4`, que varia de verdade.

## Paralelismo

As consultas "antes" quase sempre aparecem com `Parallel Seq Scan` e dois ou
três workers. Isso não foi desligado de propósito: é o que aconteceria em um
servidor real, e desligar deixaria o ganho dos índices artificialmente maior.
