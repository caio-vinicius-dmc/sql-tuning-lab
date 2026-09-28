SELECT c.uf,
       count(*)            AS qtd_pedidos,
       sum(p.valor_total)  AS faturamento
FROM clientes c
JOIN pedidos  p ON p.cliente_id = c.id
WHERE c.uf = 'PR'
  AND p.criado_em >= timestamptz '2024-01-01'
  AND p.criado_em <  timestamptz '2024-04-01'
GROUP BY c.uf;
