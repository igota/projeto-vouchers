-- Executado automaticamente pelo container MySQL na primeira inicialização
-- (docker-entrypoint-initdb.d). Schema extraído de `banco de dados/script_vouchers.sql`
-- (aquele arquivo tem comandos de rascunho/manutenção misturados e não pode
-- ser montado diretamente aqui).

CREATE TABLE IF NOT EXISTS vouchers_disponiveis (
    id INT PRIMARY KEY AUTO_INCREMENT,
    numero_voucher VARCHAR(50) NOT NULL UNIQUE,
    periodo VARCHAR(50) NOT NULL,
    status ENUM('disponivel', 'usado') DEFAULT 'disponivel',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_status (status),
    INDEX idx_periodo (periodo)
);

CREATE TABLE IF NOT EXISTS vouchers_impressos (
    id INT PRIMARY KEY AUTO_INCREMENT,
    voucher_id INT NOT NULL,
    numero_cartao VARCHAR(50) NOT NULL,
    nome_completo VARCHAR(255) NOT NULL,
    tipo_usuario VARCHAR(100) NOT NULL,
    data_impressao DATETIME NOT NULL,
    id_credencial VARCHAR(50) NULL,

    FOREIGN KEY (voucher_id) REFERENCES vouchers_disponiveis(id),
    INDEX idx_cartao (numero_cartao),
    INDEX idx_data_impressao (data_impressao),
    INDEX idx_id_credencial (id_credencial)
);

-- Sessões de login do painel /gerencia (backend/gerencia.py). Fica no banco
-- (não em memória do processo Flask) porque o Gunicorn roda vários workers
-- e um dict em memória não é visto pelos outros processos.
CREATE TABLE IF NOT EXISTS gerencia_sessoes (
    token VARCHAR(64) PRIMARY KEY,
    username VARCHAR(100) NOT NULL,
    expires_at DATETIME NOT NULL,

    INDEX idx_expires (expires_at)
);
