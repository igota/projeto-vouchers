CREATE DATABASE vouchers_db;

UPDATE mysql.user SET Host='%' WHERE User='root' AND Host='localhost';
FLUSH PRIVILEGES;
USE vouchers_db;

select * from vouchers_estoque;
select * from vouchers_gerados;
drop table vouchers_estoque;
drop table vouchers_gerados;

SELECT 
    periodo,
    COUNT(*) as quantidade_total,
    SUM(CASE WHEN status = 'disponivel' THEN 1 ELSE 0 END) as disponiveis,
    SUM(CASE WHEN status = 'usado' THEN 1 ELSE 0 END) as usados,
    CONCAT(ROUND(SUM(CASE WHEN status = 'disponivel' THEN 1 ELSE 0 END) / COUNT(*) * 100, 2), '%') as perc_disponivel
FROM vouchers_estoque 
GROUP BY periodo
ORDER BY 
    FIELD(periodo, '8horas', '1dia', '365dias');

-- =====================================================
-- Tabela 1: vouchers_estoque (Estoque de vouchers)
-- =====================================================
CREATE TABLE vouchers_estoque (
    id INT PRIMARY KEY AUTO_INCREMENT,
    numero_voucher VARCHAR(50) NOT NULL UNIQUE,
    periodo VARCHAR(50) NOT NULL,
    status ENUM('disponivel', 'usado') DEFAULT 'disponivel',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_status (status),
    INDEX idx_periodo (periodo)
);

-- =====================================================
-- Tabela 2: vouchers_gerados (Histórico de impressões - SIMPLIFICADA)
-- =====================================================
CREATE TABLE vouchers_gerados (
    id INT PRIMARY KEY AUTO_INCREMENT,
    voucher_id INT NOT NULL,
    numero_cartao VARCHAR(50) NOT NULL,
    nome_completo VARCHAR(255) NOT NULL,
    tipo_usuario VARCHAR(100) NOT NULL,
    data_impressao DATETIME NOT NULL,
    id_credencial VARCHAR(50) NULL,  -- ← NOVA COLUNA
    
    FOREIGN KEY (voucher_id) REFERENCES vouchers_estoque(id),
    INDEX idx_cartao (numero_cartao),
    INDEX idx_data_impressao (data_impressao),
    INDEX idx_id_credencial (id_credencial)  -- ← NOVO ÍNDICE
);

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
  
  
  INSERT INTO usuarios (login, tipo, status) VALUES ('IGORIMS', 'ADMINISTRADOR', 'ativo');
  
  DROP TABLE usuarios; 