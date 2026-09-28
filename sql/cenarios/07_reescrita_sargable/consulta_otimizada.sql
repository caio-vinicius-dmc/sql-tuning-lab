SELECT count(*) AS pedidos, sum(valor_total) AS faturamento
FROM pedidos
WHERE criado_em >= timestamptz '2024-06-15 00:00:00'
  AND criado_em <  timestamptz '2024-06-16 00:00:00';
