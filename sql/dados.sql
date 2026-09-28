-- Geração de massa sintética direto no banco. E muito mais rápido do que
-- mandar linhas pela rede a partir do Python, e o setseed deixa o resultado
-- reprodutível: rodar duas vezes produz exatamente os mesmos dados.
--
-- Os marcadores {qtd_clientes}, {qtd_produtos} e {qtd_pedidos} são trocados
-- pelo módulo de carga. São inteiros vindos da configuração, nunca entrada
-- de usuário -- por isso a substituição simples de texto e aceitável aqui.

SELECT setseed(0.42);

INSERT INTO clientes (id, nome, email, cidade, uf, criado_em)
SELECT
    g,
    'Cliente ' || g,
    'cliente' || g || '@exemplo.invalido',
    (ARRAY['Sao Paulo','Campinas','Rio de Janeiro','Belo Horizonte','Curitiba',
           'Porto Alegre','Salvador','Recife','Fortaleza','Goiania'])[1 + (g % 10)],
    (ARRAY['SP','SP','RJ','MG','PR','RS','BA','PE','CE','GO'])[1 + (g % 10)],
    timestamptz '2023-01-01' + (g % 900) * interval '1 day'
FROM generate_series(1, {qtd_clientes}) AS g;

INSERT INTO produtos (id, nome, categoria, preco)
SELECT
    g,
    'Produto ' || g,
    (ARRAY['Eletronicos','Livros','Moda','Casa','Esporte','Games',
           'Beleza','Alimentos'])[1 + (g % 8)],
    round((random() * 480 + 20)::numeric, 2)
FROM generate_series(1, {qtd_produtos}) AS g;

INSERT INTO pedidos (id, cliente_id, criado_em, status, valor_total)
SELECT
    g,
    1 + (random() * ({qtd_clientes} - 1))::int,
    -- dois anos de histórico, com hora aleatória dentro do dia
    timestamptz '2024-01-01'
        + (random() * 730)::int * interval '1 day'
        + (random() * 86399)::int * interval '1 second',
    CASE
        WHEN random() < 0.008 THEN 'cancelado'   -- ~0,8% do total
        WHEN random() < 0.120 THEN 'pendente'
        WHEN random() < 0.300 THEN 'enviado'
        ELSE 'entregue'
    END,
    round((random() * 1900 + 30)::numeric, 2)
FROM generate_series(1, {qtd_pedidos}) AS g;

-- Entre 1 e 4 itens por pedido. A quantidade de itens vem do próprio id em
-- vez de random(): dentro de um LATERAL o planejador pode avaliar a função
-- volátil uma única vez, e todos os pedidos acabariam com o mesmo tamanho.
INSERT INTO itens_pedido (id, pedido_id, produto_id, quantidade, preco_unitario)
SELECT
    row_number() OVER (),
    p.id,
    1 + (random() * ({qtd_produtos} - 1))::int,
    1 + (random() * 3)::int,
    round((random() * 480 + 20)::numeric, 2)
FROM pedidos p
CROSS JOIN LATERAL generate_series(1, 1 + (p.id % 4)) AS n;

-- Sem estatísticas atualizadas o planejador erra as estimativas e a
-- comparação entre os planos perde o sentido.
ANALYZE clientes;
ANALYZE produtos;
ANALYZE pedidos;
ANALYZE itens_pedido;
