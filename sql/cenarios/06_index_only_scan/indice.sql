-- INCLUDE carrega "quantidade" nas folhas do índice sem gastar espaço na
-- chave de ordenação. Com isso o plano vira Index Only Scan e a tabela
-- (heap) não precisa ser lida.
CREATE INDEX idx_itens_produto_cobertura
    ON itens_pedido (produto_id) INCLUDE (quantidade);
