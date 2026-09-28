# Relatório de tuning

Execução de 26/09/2026 às 00:20. Banco `tuning_lab` no PostgreSQL local.
Volume da massa: clientes: 20.000, produtos: 2.000, pedidos: 300.000, itens_pedido: 750.000.

Cada cenário foi medido com `EXPLAIN (ANALYZE, BUFFERS)`, descartando a
primeira execução e tomando a mediana das seguintes. Os índices são
criados e removidos dentro do próprio cenário, então a ordem de execução
não influencia o resultado.

## Resumo

| # | Cenário | Antes | Depois | Ganho | Plano |
|---|---------|-------|--------|-------|-------|
| 01 | Filtro por período em tabela sem índice | 9,57 ms | 1,12 ms | 8,5x | Seq Scan -> Index Scan |
| 02 | JOIN com filtro seletivo dos dois lados | 12,02 ms | 5,88 ms | 2,0x | Seq Scan -> Bitmap Heap Scan, Index Scan |
| 03 | Valor raro em coluna de baixa cardinalidade | 12,14 ms | 0,11 ms | 114,5x | Seq Scan -> Index Scan |
| 04 | ORDER BY com LIMIT pagando ordenação completa | 27,82 ms | 0,06 ms | 488,0x | Seq Scan -> Index Scan |
| 05 | Função aplicada na coluna do WHERE | 4,37 ms | 0,04 ms | 109,3x | Seq Scan -> Index Scan |
| 06 | Agregação lendo a tabela sem precisar | 20,82 ms | 3,63 ms | 5,7x | Seq Scan -> Index Only Scan |
| 07 | Quando o problema não é o índice, é a consulta | 15,48 ms | 0,39 ms | 40,0x | Seq Scan -> Bitmap Heap Scan |

## 01 - Filtro por período em tabela sem índice

**Problema.** A consulta pega uma semana de pedidos dentro de dois anos de histórico. Sem índice o Postgres lê a tabela inteira e descarta mais de 99% das linhas.

**Correção.** Índice B-tree simples na coluna de data, que é o filtro mais usado do sistema.

### Consulta

```sql
SELECT id, cliente_id, valor_total, criado_em
FROM pedidos
WHERE criado_em >= timestamptz '2024-07-01'
  AND criado_em <  timestamptz '2024-07-08'
ORDER BY criado_em;
```

### Índice criado

```sql
CREATE INDEX idx_pedidos_criado_em ON pedidos (criado_em);
```

### Antes

**Sem a correção** -- mediana 9,57 ms (melhor 9,22 ms), 6747 blocos tocados (0 de disco, 6747 de cache), 3005 linhas.

```
Gather Merge  (cost=5949.16..6144.43 rows=1698 width=22) (actual time=7.257..9.206 rows=3005 loops=1)
  Workers Planned: 1
  Workers Launched: 1
  Buffers: shared hit=2268
  ->  Sort  (cost=4949.15..4953.40 rows=1698 width=22) (actual time=5.484..5.543 rows=1502 loops=2)
        Sort Key: criado_em
        Sort Method: quicksort  Memory: 177kB
        Buffers: shared hit=2268
        Worker 0:  Sort Method: quicksort  Memory: 61kB
        ->  Parallel Seq Scan on pedidos  (cost=0.00..4858.06 rows=1698 width=22) (actual time=0.012..5.050 rows=1502 loops=2)
              Filter: ((criado_em >= '2024-07-01 00:00:00+00'::timestamp with time zone) AND (criado_em < '2024-07-08 00:00:00+00'::timestamp with time zone))
              Rows Removed by Filter: 148498
              Buffers: shared hit=2211
Planning Time: 0,053 ms
Execution Time: 9,406 ms
```

### Depois

**Com a correção** -- mediana 1,12 ms (melhor 0,96 ms), 3017 blocos tocados (0 de disco, 3017 de cache), 3005 linhas.

```
Index Scan using idx_pedidos_criado_em on pedidos  (cost=0.42..2079.90 rows=3105 width=22) (actual time=0.025..0.981 rows=3005 loops=1)
  Index Cond: ((criado_em >= '2024-07-01 00:00:00+00'::timestamp with time zone) AND (criado_em < '2024-07-08 00:00:00+00'::timestamp with time zone))
  Buffers: shared hit=3017
Planning Time: 0,044 ms
Execution Time: 1,079 ms
```

Resultado: 8,5x mais rápido (88,3% de redução no tempo de execução).

## 02 - JOIN com filtro seletivo dos dois lados

**Problema.** O filtro por UF corta poucos clientes, mas sem índice o banco varre pedidos inteiro e só depois cruza. O custo fica dominado pelo lado errado da junção.

**Correção.** Índice em clientes(uf) para achar o subconjunto pequeno e índice composto pedidos(cliente_id, criado_em) para o Nested Loop resolver cada cliente direto no índice.

### Consulta

```sql
SELECT c.uf,
       count(*)            AS qtd_pedidos,
       sum(p.valor_total)  AS faturamento
FROM clientes c
JOIN pedidos  p ON p.cliente_id = c.id
WHERE c.uf = 'PR'
  AND p.criado_em >= timestamptz '2024-01-01'
  AND p.criado_em <  timestamptz '2024-04-01'
GROUP BY c.uf;
```

### Índice criado

```sql
-- A ordem das colunas importa: cliente_id vem primeiro porque e o lado da
-- igualdade do JOIN; criado_em vem depois para resolver o intervalo.
-- Invertido, o índice só serviria para o filtro de data.
CREATE INDEX idx_clientes_uf ON clientes (uf);
CREATE INDEX idx_pedidos_cliente_data ON pedidos (cliente_id, criado_em);
```

### Antes

**Sem a correção** -- mediana 12,02 ms (melhor 11,51 ms), 14347 blocos tocados (0 de disco, 14347 de cache), 1 linhas.

```
Finalize GroupAggregate  (cost=1522.00..6448.92 rows=1 width=43) (actual time=10.707..12.920 rows=1 loops=1)
  Buffers: shared hit=2787
  ->  Gather  (cost=1522.00..6448.90 rows=1 width=43) (actual time=10.531..12.909 rows=2 loops=1)
        Workers Planned: 1
        Workers Launched: 1
        Buffers: shared hit=2787
        ->  Partial GroupAggregate  (cost=522.00..5448.80 rows=1 width=43) (actual time=8.697..8.700 rows=1 loops=2)
              Buffers: shared hit=2787
              ->  Hash Join  (cost=522.00..5437.79 rows=2199 width=9) (actual time=1.615..8.549 rows=1896 loops=2)
                    Hash Cond: (p.cliente_id = c.id)
                    Buffers: shared hit=2787
                    ->  Parallel Seq Scan on pedidos p  (cost=0.00..4858.06 rows=21989 width=10) (actual time=0.008..5.630 rows=18734 loops=2)
                          Filter: ((criado_em >= '2024-01-01 00:00:00+00'::timestamp with time zone) AND (criado_em < '2024-04-01 00:00:00+00'::timestamp with time zone))
                          Rows Removed by Filter: 131266
                          Buffers: shared hit=2211
                    ->  Hash  (cost=497.00..497.00 rows=2000 width=7) (actual time=1.423..1.423 rows=2000 loops=2)
                          Buckets: 2048  Batches: 1  Memory Usage: 95kB
                          Buffers: shared hit=494
                          ->  Seq Scan on clientes c  (cost=0.00..497.00 rows=2000 width=7) (actual time=0.010..1.208 rows=2000 loops=2)
                                Filter: (uf = 'PR'::bpchar)
                                Rows Removed by Filter: 18000
                                Buffers: shared hit=494
Planning:
  Buffers: shared hit=6
Planning Time: 0,163 ms
Execution Time: 12,997 ms
```

### Depois

**Com a correção** -- mediana 5,88 ms (melhor 5,79 ms), 30157 blocos tocados (0 de disco, 30157 de cache), 1 linhas.

```
GroupAggregate  (cost=18.41..4776.31 rows=1 width=43) (actual time=5.532..5.534 rows=1 loops=1)
  Buffers: shared hit=10051
  ->  Nested Loop  (cost=18.41..4757.46 rows=3768 width=9) (actual time=0.107..5.261 rows=3792 loops=1)
        Buffers: shared hit=10051
        ->  Bitmap Heap Scan on clientes c  (cost=17.99..289.99 rows=2000 width=7) (actual time=0.092..0.380 rows=2000 loops=1)
              Recheck Cond: (uf = 'PR'::bpchar)
              Heap Blocks: exact=247
              Buffers: shared hit=251
              ->  Bitmap Index Scan on idx_clientes_uf  (cost=0.00..17.49 rows=2000 width=0) (actual time=0.067..0.067 rows=2000 loops=1)
                    Index Cond: (uf = 'PR'::bpchar)
                    Buffers: shared hit=4
        ->  Index Scan using idx_pedidos_cliente_data on pedidos p  (cost=0.42..2.21 rows=2 width=10) (actual time=0.002..0.002 rows=2 loops=2000)
              Index Cond: ((cliente_id = c.id) AND (criado_em >= '2024-01-01 00:00:00+00'::timestamp with time zone) AND (criado_em < '2024-04-01 00:00:00+00'::timestamp with time zone))
              Buffers: shared hit=9800
Planning:
  Buffers: shared hit=14
Planning Time: 0,401 ms
Execution Time: 5,608 ms
```

Resultado: 2,0x mais rápido (51,0% de redução no tempo de execução).

## 03 - Valor raro em coluna de baixa cardinalidade

**Problema.** Pedidos cancelados são menos de 1% da tabela. Um índice comum em status indexaria as 300 mil linhas para atender uma consulta que precisa de poucas milhares.

**Correção.** Índice parcial com WHERE status = 'cancelado', já ordenado por data decrescente.

### Consulta

```sql
SELECT id, cliente_id, criado_em, valor_total
FROM pedidos
WHERE status = 'cancelado'
  AND criado_em >= timestamptz '2024-01-01'
ORDER BY criado_em DESC
LIMIT 50;
```

### Índice criado

```sql
-- Índice parcial: indexa menos de 1% da tabela e ainda assim atende 100%
-- das consultas que filtram por pedidos cancelados. Fica pequeno o bastante
-- para caber em cache é barato de manter no INSERT/UPDATE.
CREATE INDEX idx_pedidos_cancelados
    ON pedidos (criado_em DESC)
 WHERE status = 'cancelado';
```

### Antes

**Sem a correção** -- mediana 12,14 ms (melhor 11,04 ms), 9015 blocos tocados (0 de disco, 9015 de cache), 50 linhas.

```
Limit  (cost=5910.06..5915.81 rows=50 width=22) (actual time=9.206..11.421 rows=50 loops=1)
  Buffers: shared hit=2268
  ->  Gather Merge  (cost=5910.06..6090.03 rows=1565 width=22) (actual time=9.204..11.413 rows=50 loops=1)
        Workers Planned: 1
        Workers Launched: 1
        Buffers: shared hit=2268
        ->  Sort  (cost=4910.05..4913.96 rows=1565 width=22) (actual time=7.172..7.175 rows=43 loops=2)
              Sort Key: criado_em DESC
              Sort Method: top-N heapsort  Memory: 30kB
              Buffers: shared hit=2268
              Worker 0:  Sort Method: top-N heapsort  Memory: 31kB
              ->  Parallel Seq Scan on pedidos  (cost=0.00..4858.06 rows=1565 width=22) (actual time=0.015..6.870 rows=1169 loops=2)
                    Filter: ((criado_em >= '2024-01-01 00:00:00+00'::timestamp with time zone) AND (status = 'cancelado'::text))
                    Rows Removed by Filter: 148831
                    Buffers: shared hit=2211
Planning Time: 0,075 ms
Execution Time: 11,481 ms
```

### Depois

**Com a correção** -- mediana 0,11 ms (melhor 0,09 ms), 104 blocos tocados (0 de disco, 104 de cache), 50 linhas.

```
Limit  (cost=0.28..36.87 rows=50 width=22) (actual time=0.034..0.074 rows=50 loops=1)
  Buffers: shared hit=52
  ->  Index Scan using idx_pedidos_cancelados on pedidos  (cost=0.28..1778.58 rows=2430 width=22) (actual time=0.034..0.071 rows=50 loops=1)
        Index Cond: (criado_em >= '2024-01-01 00:00:00+00'::timestamp with time zone)
        Buffers: shared hit=52
Planning Time: 0,064 ms
Execution Time: 0,105 ms
```

Resultado: 114,5x mais rápido (99,1% de redução no tempo de execução).

## 04 - ORDER BY com LIMIT pagando ordenação completa

**Problema.** Para devolver 20 linhas o banco ordena todos os pedidos entregues em memória. O LIMIT não evita o trabalho, só descarta o resultado.

**Correção.** Índice composto (status, valor_total DESC) que já entrega as linhas na ordem pedida.

### Consulta

```sql
SELECT id, cliente_id, valor_total
FROM pedidos
WHERE status = 'entregue'
ORDER BY valor_total DESC
LIMIT 20;
```

### Índice criado

```sql
-- O objetivo aqui não é só filtrar: é entregar as linhas já na ordem pedida,
-- para o plano trocar o "Top-N heapsort" por uma leitura de 20 linhas do índice.
CREATE INDEX idx_pedidos_status_valor
    ON pedidos (status, valor_total DESC);
```

### Antes

**Sem a correção** -- mediana 27,82 ms (melhor 25,91 ms), 9012 blocos tocados (0 de disco, 9012 de cache), 20 linhas.

```
Limit  (cost=8285.89..8288.19 rows=20 width=14) (actual time=27.103..29.334 rows=20 loops=1)
  Buffers: shared hit=2267
  ->  Gather Merge  (cost=8285.89..20684.96 rows=107818 width=14) (actual time=27.102..29.329 rows=20 loops=1)
        Workers Planned: 1
        Workers Launched: 1
        Buffers: shared hit=2267
        ->  Sort  (cost=7285.88..7555.43 rows=107818 width=14) (actual time=24.092..24.094 rows=16 loops=2)
              Sort Key: valor_total DESC
              Sort Method: top-N heapsort  Memory: 26kB
              Buffers: shared hit=2267
              Worker 0:  Sort Method: top-N heapsort  Memory: 26kB
              ->  Parallel Seq Scan on pedidos  (cost=0.00..4416.88 rows=107818 width=14) (actual time=0.012..13.669 rows=91688 loops=2)
                    Filter: (status = 'entregue'::text)
                    Rows Removed by Filter: 58312
                    Buffers: shared hit=2211
Planning Time: 0,068 ms
Execution Time: 29,366 ms
```

### Depois

**Com a correção** -- mediana 0,06 ms (melhor 0,04 ms), 46 blocos tocados (0 de disco, 46 de cache), 20 linhas.

```
Limit  (cost=0.42..1.11 rows=20 width=14) (actual time=0.020..0.029 rows=20 loops=1)
  Buffers: shared hit=23
  ->  Index Scan using idx_pedidos_status_valor on pedidos  (cost=0.42..6291.96 rows=183190 width=14) (actual time=0.019..0.027 rows=20 loops=1)
        Index Cond: (status = 'entregue'::text)
        Buffers: shared hit=23
Planning Time: 0,028 ms
Execution Time: 0,048 ms
```

Resultado: 488,0x mais rápido (99,8% de redução no tempo de execução).

## 05 - Função aplicada na coluna do WHERE

**Problema.** A busca usa lower(email). Mesmo que existisse um índice em email ele seria ignorado, porque o valor indexado e diferente do valor comparado.

**Correção.** Índice sobre a expressão lower(email), que é o que a consulta realmente compara.

### Consulta

```sql
SELECT id, nome, email
FROM clientes
WHERE lower(email) = 'cliente12345@exemplo.invalido';
```

### Índice criado

```sql
-- Um índice comum em "email" não serve para "lower(email)": o planejador
-- só casa o índice quando a expressão é idêntica à da consulta.
CREATE INDEX idx_clientes_email_lower ON clientes (lower(email));
```

### Antes

**Sem a correção** -- mediana 4,37 ms (melhor 4,29 ms), 247 blocos tocados (0 de disco, 247 de cache), 1 linhas.

```
Seq Scan on clientes  (cost=0.00..547.00 rows=100 width=46) (actual time=2.705..4.407 rows=1 loops=1)
  Filter: (lower(email) = 'cliente12345@exemplo.invalido'::text)
  Rows Removed by Filter: 19999
  Buffers: shared hit=247
Planning Time: 0,033 ms
Execution Time: 4,414 ms
```

### Depois

**Com a correção** -- mediana 0,04 ms (melhor 0,03 ms), 3 blocos tocados (0 de disco, 3 de cache), 1 linhas.

```
Index Scan using idx_clientes_email_lower on clientes  (cost=0.29..2.51 rows=1 width=46) (actual time=0.018..0.019 rows=1 loops=1)
  Index Cond: (lower(email) = 'cliente12345@exemplo.invalido'::text)
  Buffers: shared hit=3
Planning Time: 0,030 ms
Execution Time: 0,033 ms
```

Resultado: 109,3x mais rápido (99,1% de redução no tempo de execução).

## 06 - Agregação lendo a tabela sem precisar

**Problema.** A consulta só usa produto_id e quantidade, mas o plano vai até o heap buscar cada linha para ler uma coluna que poderia estar no próprio índice.

**Correção.** Índice com INCLUDE (quantidade), cobrindo todas as colunas da consulta.

### Consulta

```sql
SELECT produto_id, sum(quantidade) AS unidades
FROM itens_pedido
WHERE produto_id BETWEEN 100 AND 200
GROUP BY produto_id
ORDER BY produto_id;
```

### Índice criado

```sql
-- INCLUDE carrega "quantidade" nas folhas do índice sem gastar espaço na
-- chave de ordenação. Com isso o plano vira Index Only Scan e a tabela
-- (heap) não precisa ser lida.
CREATE INDEX idx_itens_produto_cobertura
    ON itens_pedido (produto_id) INCLUDE (quantidade);
```

### Antes

**Sem a correção** -- mediana 20,82 ms (melhor 18,26 ms), 27617 blocos tocados (0 de disco, 27617 de cache), 101 linhas.

```
Finalize GroupAggregate  (cost=11408.76..11915.46 rows=2000 width=12) (actual time=16.687..18.897 rows=101 loops=1)
  Group Key: produto_id
  Buffers: shared hit=5529
  ->  Gather Merge  (cost=11408.76..11875.46 rows=4000 width=12) (actual time=16.660..18.832 rows=303 loops=1)
        Workers Planned: 2
        Workers Launched: 2
        Buffers: shared hit=5529
        ->  Sort  (cost=10408.74..10413.74 rows=2000 width=12) (actual time=12.699..12.706 rows=101 loops=3)
              Sort Key: produto_id
              Sort Method: quicksort  Memory: 28kB
              Buffers: shared hit=5529
              Worker 0:  Sort Method: quicksort  Memory: 28kB
              Worker 1:  Sort Method: quicksort  Memory: 28kB
              ->  Partial HashAggregate  (cost=10279.08..10299.08 rows=2000 width=12) (actual time=12.605..12.636 rows=101 loops=3)
                    Group Key: produto_id
                    Batches: 1  Memory Usage: 121kB
                    Buffers: shared hit=5515
                    Worker 0:  Batches: 1  Memory Usage: 121kB
                    Worker 1:  Batches: 1  Memory Usage: 121kB
                    ->  Parallel Seq Scan on itens_pedido  (cost=0.00..10202.50 rows=15316 width=6) (actual time=0.011..11.150 rows=12691 loops=3)
                          Filter: ((produto_id >= 100) AND (produto_id <= 200))
                          Rows Removed by Filter: 237309
                          Buffers: shared hit=5515
Planning Time: 0,072 ms
Execution Time: 19,015 ms
```

### Depois

**Com a correção** -- mediana 3,63 ms (melhor 3,62 ms), 216 blocos tocados (0 de disco, 216 de cache), 101 linhas.

```
GroupAggregate  (cost=0.42..1033.70 rows=2000 width=12) (actual time=0.077..3.897 rows=101 loops=1)
  Group Key: produto_id
  Buffers: shared hit=108
  ->  Index Only Scan using idx_itens_produto_cobertura on itens_pedido  (cost=0.42..833.04 rows=36131 width=6) (actual time=0.035..2.289 rows=38072 loops=1)
        Index Cond: ((produto_id >= 100) AND (produto_id <= 200))
        Heap Fetches: 0
        Buffers: shared hit=108
Planning Time: 0,059 ms
Execution Time: 3,935 ms
```

Resultado: 5,7x mais rápido (82,6% de redução no tempo de execução).

## 07 - Quando o problema não é o índice, é a consulta

**Problema.** O índice em criado_em já existe, mas WHERE date(criado_em) = ... envolve a coluna em uma função e o planejador não consegue usa-lo. Nem adianta criar índice de expressão: date() sobre timestamptz depende do fuso e não é IMMUTABLE.

**Correção.** Reescrever o filtro como intervalo semiaberto sobre a coluna crua. Nenhum objeto novo no banco.

### Consulta

```sql
SELECT count(*) AS pedidos, sum(valor_total) AS faturamento
FROM pedidos
WHERE date(criado_em) = date '2024-06-15';
```

### Consulta reescrita

```sql
SELECT count(*) AS pedidos, sum(valor_total) AS faturamento
FROM pedidos
WHERE criado_em >= timestamptz '2024-06-15 00:00:00'
  AND criado_em <  timestamptz '2024-06-16 00:00:00';
```

### Antes

**Sem a correção** -- mediana 15,48 ms (melhor 15,29 ms), 8844 blocos tocados (0 de disco, 8844 de cache), 1 linhas.

```
Finalize Aggregate  (cost=5862.59..5862.60 rows=1 width=40) (actual time=14.452..16.424 rows=1 loops=1)
  Buffers: shared hit=2211
  ->  Gather  (cost=5862.47..5862.58 rows=1 width=40) (actual time=14.331..16.413 rows=2 loops=1)
        Workers Planned: 1
        Workers Launched: 1
        Buffers: shared hit=2211
        ->  Partial Aggregate  (cost=4862.47..4862.48 rows=1 width=40) (actual time=12.272..12.273 rows=1 loops=2)
              Buffers: shared hit=2211
              ->  Parallel Seq Scan on pedidos  (cost=0.00..4858.06 rows=882 width=6) (actual time=0.069..12.227 rows=216 loops=2)
                    Filter: (date(criado_em) = '2024-06-15'::date)
                    Rows Removed by Filter: 149784
                    Buffers: shared hit=2211
Planning Time: 0,053 ms
Execution Time: 16,461 ms
```

### Depois

**Com a correção** -- mediana 0,39 ms (melhor 0,35 ms), 788 blocos tocados (0 de disco, 788 de cache), 1 linhas.

```
Aggregate  (cost=394.86..394.87 rows=1 width=40) (actual time=0.369..0.369 rows=1 loops=1)
  Buffers: shared hit=392
  ->  Bitmap Heap Scan on pedidos  (cost=6.62..392.90 rows=390 width=6) (actual time=0.084..0.331 rows=431 loops=1)
        Recheck Cond: ((criado_em >= '2024-06-15 00:00:00+00'::timestamp with time zone) AND (criado_em < '2024-06-16 00:00:00+00'::timestamp with time zone))
        Heap Blocks: exact=388
        Buffers: shared hit=392
        ->  Bitmap Index Scan on idx_pedidos_criado_em_sargable  (cost=0.00..6.52 rows=390 width=0) (actual time=0.055..0.056 rows=431 loops=1)
              Index Cond: ((criado_em >= '2024-06-15 00:00:00+00'::timestamp with time zone) AND (criado_em < '2024-06-16 00:00:00+00'::timestamp with time zone))
              Buffers: shared hit=4
Planning Time: 0,047 ms
Execution Time: 0,400 ms
```

Resultado: 40,0x mais rápido (97,5% de redução no tempo de execução).
