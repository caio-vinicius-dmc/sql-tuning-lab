SELECT id, nome, email
FROM clientes
WHERE lower(email) = 'cliente12345@exemplo.invalido';
