CREATE DATABASE vouchers_db;

UPDATE mysql.user SET Host='%' WHERE User='root' AND Host='localhost';
FLUSH PRIVILEGES;
USE vouchers_db;

select * from vouchers_disponiveis;
select * from vouchers_impressos;
drop table vouchers_disponiveis;
drop table vouchers_impressos;

SELECT 
    periodo,
    COUNT(*) as quantidade_total,
    SUM(CASE WHEN status = 'disponivel' THEN 1 ELSE 0 END) as disponiveis,
    SUM(CASE WHEN status = 'usado' THEN 1 ELSE 0 END) as usados,
    CONCAT(ROUND(SUM(CASE WHEN status = 'disponivel' THEN 1 ELSE 0 END) / COUNT(*) * 100, 2), '%') as perc_disponivel
FROM vouchers_disponiveis 
GROUP BY periodo
ORDER BY 
    FIELD(periodo, '8horas', '1dia', '365dias');

-- =====================================================
-- Tabela 1: vouchers_disponiveis (Estoque de vouchers)
-- =====================================================
CREATE TABLE vouchers_disponiveis (
    id INT PRIMARY KEY AUTO_INCREMENT,
    numero_voucher VARCHAR(50) NOT NULL UNIQUE,
    periodo VARCHAR(50) NOT NULL,
    status ENUM('disponivel', 'usado') DEFAULT 'disponivel',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_status (status),
    INDEX idx_periodo (periodo)
);

-- =====================================================
-- Tabela 2: vouchers_impressos (Histórico de impressões - SIMPLIFICADA)
-- =====================================================
CREATE TABLE vouchers_impressos (
    id INT PRIMARY KEY AUTO_INCREMENT,
    voucher_id INT NOT NULL,
    numero_cartao VARCHAR(50) NOT NULL,
    nome_completo VARCHAR(255) NOT NULL,
    tipo_usuario VARCHAR(100) NOT NULL,
    data_impressao DATETIME NOT NULL,
    id_credencial VARCHAR(50) NULL,  -- ← NOVA COLUNA
    
    FOREIGN KEY (voucher_id) REFERENCES vouchers_disponiveis(id),
    INDEX idx_cartao (numero_cartao),
    INDEX idx_data_impressao (data_impressao),
    INDEX idx_id_credencial (id_credencial)  -- ← NOVO ÍNDICE
);

