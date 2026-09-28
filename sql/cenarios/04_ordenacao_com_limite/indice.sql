-- O objetivo aqui não é só filtrar: é entregar as linhas já na ordem pedida,
-- para o plano trocar o "Top-N heapsort" por uma leitura de 20 linhas do índice.
CREATE INDEX idx_pedidos_status_valor
    ON pedidos (status, valor_total DESC);
