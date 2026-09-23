-- Executado automaticamente pelo container MySQL na primeira inicialização
-- (docker-entrypoint-initdb.d). Schema extraído de `banco de dados/script_vouchers.sql`
-- (aquele arquivo tem comandos de rascunho/manutenção misturados e não pode
-- ser montado diretamente aqui).

CREATE TABLE IF NOT EXISTS vouchers_estoque (
    id INT PRIMARY KEY AUTO_INCREMENT,
    numero_voucher VARCHAR(50) NOT NULL UNIQUE,
    periodo VARCHAR(50) NOT NULL,
    status ENUM('disponivel', 'usado') DEFAULT 'disponivel',
    -- 'totem': gerado em lote pela reposição automática de estoque, fica
    -- 'disponivel' até o totem entregar pra alguém. 'gerencia': gerado sob
    -- demanda pelo painel /gerencia pra uma pessoa específica — já nasce
    -- 'usado' (nunca fica disponível pro totem pegar).
    origem ENUM('gerencia', 'totem') NOT NULL DEFAULT 'totem',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_status (status),
    INDEX idx_periodo (periodo)
);

CREATE TABLE IF NOT EXISTS vouchers_gerados (
    id INT PRIMARY KEY AUTO_INCREMENT,
    voucher_id INT NOT NULL,
    numero_cartao VARCHAR(50) NOT NULL,
    nome_completo VARCHAR(255) NOT NULL,
    tipo_usuario VARCHAR(100) NOT NULL,
    data_impressao DATETIME NOT NULL,
    id_credencial VARCHAR(50) NULL,

    FOREIGN KEY (voucher_id) REFERENCES vouchers_estoque(id),
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

-- Quem pode logar no /gerencia e com qual papel. Substitui o antigo
-- allowlist plano em json/usuarios_permitidos.json — fica no banco pelo
-- mesmo motivo de gerencia_sessoes (múltiplos workers do Gunicorn). `nome`
-- e `ultimo_acesso` são preenchidos automaticamente no login (capturados
-- do Vitae), não digitados no cadastro.
CREATE TABLE IF NOT EXISTS usuarios (
    id INT PRIMARY KEY AUTO_INCREMENT,
    login VARCHAR(100) NOT NULL UNIQUE,
    nome VARCHAR(255) NULL,
    tipo ENUM('COORDENADOR', 'ADMINISTRADOR') NOT NULL DEFAULT 'COORDENADOR',
    status ENUM('ativo', 'inativo') NOT NULL DEFAULT 'ativo',
    ultimo_acesso DATETIME NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_login (login),
    INDEX idx_status (status)
);
