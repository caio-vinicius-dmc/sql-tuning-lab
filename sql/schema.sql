-- Modelo de e-commerce simplificado usado como cobaia do laboratório.
-- De propósito não existe nenhum índice além das chaves primárias: cada
-- cenário cria o seu, para que a diferença no plano fique evidente.

DROP TABLE IF EXISTS itens_pedido CASCADE;
DROP TABLE IF EXISTS pedidos CASCADE;
DROP TABLE IF EXISTS produtos CASCADE;
DROP TABLE IF EXISTS clientes CASCADE;

CREATE TABLE clientes (
    id          integer PRIMARY KEY,
    nome        text        NOT NULL,
    email       text        NOT NULL,
    cidade      text        NOT NULL,
    uf          char(2)     NOT NULL,
    criado_em   timestamptz NOT NULL
);

CREATE TABLE produtos (
    id         integer PRIMARY KEY,
    nome       text          NOT NULL,
    categoria  text          NOT NULL,
    preco      numeric(10,2) NOT NULL
);

CREATE TABLE pedidos (
    id          integer PRIMARY KEY,
    cliente_id  integer       NOT NULL REFERENCES clientes (id),
    criado_em   timestamptz   NOT NULL,
    -- distribuição intencionalmente desbalanceada: 'cancelado' é raro,
    -- o que torna o índice parcial do cenário 03 interessante
    status      text          NOT NULL,
    valor_total numeric(12,2) NOT NULL
);

CREATE TABLE itens_pedido (
    id             bigint PRIMARY KEY,
    pedido_id      integer       NOT NULL REFERENCES pedidos (id),
    produto_id     integer       NOT NULL REFERENCES produtos (id),
    quantidade     smallint      NOT NULL,
    preco_unitario numeric(10,2) NOT NULL
);
