-- O índice já existe antes da medição "antes". A questao deste cenário não
-- e a falta de índice, e a consulta estar escrita de um jeito que impede o uso.
CREATE INDEX idx_pedidos_criado_em_sargable ON pedidos (criado_em);
