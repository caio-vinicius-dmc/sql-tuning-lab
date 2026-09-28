-- A ordem das colunas importa: cliente_id vem primeiro porque e o lado da
-- igualdade do JOIN; criado_em vem depois para resolver o intervalo.
-- Invertido, o índice só serviria para o filtro de data.
CREATE INDEX idx_clientes_uf ON clientes (uf);
CREATE INDEX idx_pedidos_cliente_data ON pedidos (cliente_id, criado_em);
