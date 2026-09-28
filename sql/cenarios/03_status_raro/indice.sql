-- Índice parcial: indexa menos de 1% da tabela e ainda assim atende 100%
-- das consultas que filtram por pedidos cancelados. Fica pequeno o bastante
-- para caber em cache é barato de manter no INSERT/UPDATE.
CREATE INDEX idx_pedidos_cancelados
    ON pedidos (criado_em DESC)
 WHERE status = 'cancelado';
