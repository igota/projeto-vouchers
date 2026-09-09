# voucher_service.py (simplificado para 1 dia)
import os
import requests
import json
import time
import urllib3
from dotenv import load_dotenv
from typing import Optional, List, Dict, Any
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from conexao import get_db_connection

load_dotenv()
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

DURACAO_REPOSICAO_MINUTOS_PADRAO = int(os.environ.get('VOUCHER_REPOSICAO_DURACAO_MINUTOS', 1440))


class VoucherService:
    def __init__(self):
        self.base_url = os.environ['OMADA_BASE_URL']
        self.site_id = os.environ['OMADA_SITE_ID']
        self.username = os.environ['OMADA_USERNAME']
        self.password = os.environ['OMADA_PASSWORD']
        self.session = requests.Session()
        self.session.verify = False
        self.token = None
    
    def login(self) -> bool:
        """Login e obtém token"""
        print('🔐 Fazendo login...')
        
        headers = {
            'Content-Type': 'application/json',
            'X-Requested-With': 'XMLHttpRequest',
            'Referer': f'{self.base_url}/login#hotspot'
        }
        
        payload = {'name': self.username, 'password': self.password}
        
        try:
            response = self.session.post(
                f'{self.base_url}/api/v2/hotspot/login',
                json=payload,
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('errorCode') == 0:
                    self.token = data.get('result', {}).get('token')
                    print(f'✅ Login OK! Token: {self.token[:20]}...')
                    return True
            return False
        except Exception as e:
            print(f'❌ Erro no login: {e}')
            return False
    
    def gerar_voucher(self, duration_minutes: int, note: str) -> Optional[str]:
        headers = {
            'Content-Type': 'application/json',
            'X-Requested-With': 'XMLHttpRequest',
            'Referer': f'{self.base_url}/login#hotspot',
            'Csrf-Token': self.token
        }
        
        payload = {
            "codeLength": 6,
            "amount": 1,
            "type": 0,
            "rateLimitId": "6a43b553c95ed17c8b77cad1",  # ← ADICIONE AQUI
            "trafficLimitEnable": False,
            "durationType": 1,
            "duration": duration_minutes,
            "note": note,
            "maxUsers": 1,
            "portals": ["64d105ba0755dc793d5cff1e"]
        }
        
        try:
            response = self.session.post(
                f'{self.base_url}/api/v2/hotspot/sites/{self.site_id}/vouchers',
                json=payload,
                headers=headers,
                timeout=30
            )
            
            if response.status_code != 200:
                return None
            
            data = response.json()
            if data.get('errorCode') != 0:
                return None
            
            result = data.get('result', {})
            codigo = result.get('code') or result.get('codes', [None])[0]
            
            # Fallback: buscar da lista
            if not codigo:
                time.sleep(0.5)
                response = self.session.get(
                    f'{self.base_url}/api/v2/hotspot/sites/{self.site_id}/vouchers',
                    params={'currentPage': 1, 'currentPageSize': 5, 'note': note},
                    headers=headers,
                    timeout=30
                )
                if response.status_code == 200:
                    data = response.json()
                    for v in data.get('result', {}).get('data', []):
                        if v.get('note') == note:
                            codigo = v.get('code')
                            break
            
            return codigo
        except Exception as e:
            return None


def gerar_e_inserir_vouchers(quantidade: int = 10, max_workers: int = 3, delay: float = 0.3,
                              duracao_minutos: int = None):
    """Gera vouchers de reposição e insere no banco"""
    duracao_minutos = duracao_minutos or DURACAO_REPOSICAO_MINUTOS_PADRAO

    print("="*50)
    print(f"🔍 [GERAR] FUNÇÃO GERAR CHAMADA - quantidade: {quantidade}")
    print("="*50)
    print("\n" + "="*60)
    print("🎟️ GERANDO VOUCHERS DE REPOSIÇÃO")
    print(f"📦 Quantidade: {quantidade}")
    print(f"⏱️ Duração: {duracao_minutos} minutos")
    print(f"🚀 Workers: {max_workers}")
    print("="*60)

    service = VoucherService()
    if not service.login():
        print("❌ Falha no login")
        return False

    data_atual = datetime.now().strftime('%Y%m%d')

    tarefas = []
    for i in range(quantidade):
        nome = f"VOUCHER_1DIA_{data_atual}_{i+1:03d}"
        tarefas.append(('1dia', duracao_minutos, nome))
    
    resultados = []
    sucessos = 0
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = []
        for i, (periodo, duracao, nome) in enumerate(tarefas):
            future = executor.submit(service.gerar_voucher, duracao, nome)
            futures.append((future, periodo, nome))
            if i < len(tarefas) - 1:
                time.sleep(delay)
        
        for future, periodo, nome in futures:
            try:
                codigo = future.result(timeout=60)
                if codigo:
                    resultados.append({'codigo': codigo, 'periodo': periodo, 'created_at': datetime.now()})
                    sucessos += 1
                    print(f"   ✅ {codigo}")
                else:
                    print(f"   ❌ Falha: {nome}")
            except Exception as e:
                print(f"   ❌ Erro: {e}")
    
    # Inserir no banco
    if resultados:
        connection = get_db_connection()
        try:
            with connection.cursor() as cursor:
                sql = """
                    INSERT INTO vouchers_disponiveis 
                    (numero_voucher, periodo, status, created_at) 
                    VALUES (%s, %s, %s, %s)
                """
                dados = [(r['codigo'], r['periodo'], 'disponivel', r['created_at']) for r in resultados]
                cursor.executemany(sql, dados)
                connection.commit()
                print(f"\n💾 {len(resultados)} vouchers inseridos no banco")
        except Exception as e:
            print(f"❌ Erro no insert: {e}")
            return False
        finally:
            connection.close()
    
    print(f"\n✅ Sucessos: {sucessos} | ❌ Falhas: {quantidade - sucessos}")
    return sucessos > 0


def verificar_estoque():
    """Verifica estoque de vouchers de 1 dia"""
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT COUNT(*) as total,
                       SUM(CASE WHEN status = 'disponivel' THEN 1 ELSE 0 END) as disponiveis
                FROM vouchers_disponiveis 
                WHERE periodo = '1dia'
            """)
            row = cursor.fetchone()
            print("\n📊 ESTOQUE DE VOUCHERS (1 DIA)")
            print(f"   Disponíveis: {row['disponiveis']} / {row['total']} total")
    finally:
        connection.close()


if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1:
        comando = sys.argv[1]
        if comando == 'gerar':
            qtd = int(sys.argv[2]) if len(sys.argv) > 2 else 10
            gerar_e_inserir_vouchers(qtd)
        elif comando == 'verificar':
            verificar_estoque()
    else:
        gerar_e_inserir_vouchers(10)