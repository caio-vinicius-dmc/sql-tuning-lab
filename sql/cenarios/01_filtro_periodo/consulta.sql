SELECT id, cliente_id, valor_total, criado_em
FROM pedidos
WHERE criado_em >= timestamptz '2024-07-01'
  AND criado_em <  timestamptz '2024-07-08'
ORDER BY criado_em;
