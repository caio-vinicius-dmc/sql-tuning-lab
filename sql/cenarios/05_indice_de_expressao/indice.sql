-- Um índice comum em "email" não serve para "lower(email)": o planejador
-- só casa o índice quando a expressão é idêntica à da consulta.
CREATE INDEX idx_clientes_email_lower ON clientes (lower(email));
