SELECT id, cliente_id, valor_total
FROM pedidos
WHERE status = 'entregue'
ORDER BY valor_total DESC
LIMIT 20;
