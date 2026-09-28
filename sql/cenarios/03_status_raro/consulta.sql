SELECT id, cliente_id, criado_em, valor_total
FROM pedidos
WHERE status = 'cancelado'
  AND criado_em >= timestamptz '2024-01-01'
ORDER BY criado_em DESC
LIMIT 50;
