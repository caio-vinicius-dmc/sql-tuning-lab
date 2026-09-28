SELECT produto_id, sum(quantidade) AS unidades
FROM itens_pedido
WHERE produto_id BETWEEN 100 AND 200
GROUP BY produto_id
ORDER BY produto_id;
