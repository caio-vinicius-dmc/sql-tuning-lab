SELECT count(*) AS pedidos, sum(valor_total) AS faturamento
FROM pedidos
WHERE date(criado_em) = date '2024-06-15';
