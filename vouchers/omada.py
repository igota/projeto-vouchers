import os
import time

import requests
import urllib3
from dotenv import load_dotenv
from typing import Optional, Dict

load_dotenv()
urllib3.disable_warnings()

OMADA_BASE_URL = os.environ['OMADA_BASE_URL']
OMADA_SITE_ID  = os.environ['OMADA_SITE_ID']

_token: Optional[str] = None
_session = requests.Session()
_session.verify = False


def _headers_auth() -> dict:
    return {
        'Content-Type': 'application/json',
        'X-Requested-With': 'XMLHttpRequest',
        'Referer': f'{OMADA_BASE_URL}/login#hotspot',
        'Csrf-Token': _token or '',
    }


def login_omada() -> bool:
    global _token
    try:
        resp = _session.post(
            f'{OMADA_BASE_URL}/api/v2/hotspot/login',
            json={'name': os.environ['OMADA_USERNAME'], 'password': os.environ['OMADA_PASSWORD']},
            headers={
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest',
                'Referer': f'{OMADA_BASE_URL}/login#hotspot',
            },
            timeout=30,
        )
        if resp.status_code == 200:
            data = resp.json()
            if data.get('errorCode') == 0:
                _token = data.get('result', {}).get('token')
                print(f'✅ Login Omada OK!')
                return True
        print('❌ Falha no login Omada')
        return False
    except Exception as e:
        print(f'❌ Erro no login Omada: {e}')
        return False


def _chamar_api(metodo: str, url: str, _retry: bool = True, **kwargs) -> Optional[dict]:
    """Chamada autenticada à API Omada. Re-autentica automaticamente se a sessão expirar."""
    global _token
    if not _token:
        if not login_omada():
            return None
    kwargs['headers'] = _headers_auth()
    kwargs.setdefault('timeout', 30)
    try:
        resp = getattr(_session, metodo)(url, **kwargs)
        if resp.status_code != 200:
            print(f'❌ HTTP {resp.status_code}')
            return None
        data = resp.json()
        if data.get('errorCode') == 0:
            return data
        # errorCode < 0 indica sessão expirada no Omada
        if _retry and data.get('errorCode', 0) < 0:
            print(f'🔄 Sessão Omada expirada (code={data.get("errorCode")}), re-autenticando...')
            _token = None
            return _chamar_api(metodo, url, _retry=False, **kwargs)
        print(f'❌ Erro Omada: {data.get("msg")}')
        return None
    except Exception as e:
        print(f'❌ Erro API Omada: {e}')
        return None


def buscar_cliente_por_voucher(voucher_code: str) -> Optional[Dict]:
    data = _chamar_api(
        'get',
        f'{OMADA_BASE_URL}/api/v2/hotspot/sites/{OMADA_SITE_ID}/clients',
        params={'currentPage': 1, 'currentPageSize': 10, 'searchKey': voucher_code},
    )
    if data:
        for client in data.get('result', {}).get('data', []):
            if client.get('voucherCode') == voucher_code:
                print(f"✅ Cliente encontrado: {client.get('id')} - Valid: {client.get('valid')}")
                print(f"   Campos disponíveis: {list(client.keys())}")
                return client
    print(f"❌ Voucher {voucher_code} não encontrado no Omada")
    return None


def gerar_voucher_omada(duracao_minutos: int, note: str) -> Optional[str]:
    payload = {
        "codeLength": 6,
        "amount": 1,
        "type": 0,
        "durationType": 1,
        "duration": duracao_minutos,
        "note": note,
        "maxUsers": 1,
        "portals": ["64d105ba0755dc793d5cff1e"]
    }
    data = _chamar_api(
        'post',
        f'{OMADA_BASE_URL}/api/v2/hotspot/sites/{OMADA_SITE_ID}/vouchers',
        json=payload,
    )
    if not data:
        return None

    print(f'✅ Voucher gerado no Omada: {duracao_minutos} minutos')
    time.sleep(1)

    data2 = _chamar_api(
        'get',
        f'{OMADA_BASE_URL}/api/v2/hotspot/sites/{OMADA_SITE_ID}/vouchers',
        params={'currentPage': 1, 'currentPageSize': 10, 'note': note},
    )
    if data2:
        for v in data2.get('result', {}).get('data', []):
            if v.get('note') == note:
                codigo = v.get('code')
                print(f'✅ Código: {codigo}')
                return codigo

    print('❌ Não foi possível obter o código do voucher')
    return None


def deletar_voucher_omada(voucher_code: str) -> bool:
    """Deleta um voucher não utilizado do Omada (antes de ser usado)."""
    data = _chamar_api(
        'get',
        f'{OMADA_BASE_URL}/api/v2/hotspot/sites/{OMADA_SITE_ID}/vouchers',
        params={'currentPage': 1, 'currentPageSize': 50},
    )
    if data:
        for v in data.get('result', {}).get('data', []):
            if v.get('code') == voucher_code:
                voucher_id = v.get('id')
                del_data = _chamar_api(
                    'delete',
                    f'{OMADA_BASE_URL}/api/v2/hotspot/sites/{OMADA_SITE_ID}/vouchers/{voucher_id}',
                )
                if del_data is not None:
                    print(f'✅ Voucher {voucher_code} deletado do Omada')
                    return True
                print(f'❌ Falha ao deletar voucher {voucher_code}')
                return False
    print(f'❌ Voucher {voucher_code} não encontrado na lista do Omada')
    return False


def cancelar_cliente(client_id: str) -> bool:
    data = _chamar_api(
        'delete',
        f'{OMADA_BASE_URL}/api/v2/hotspot/sites/{OMADA_SITE_ID}/clients/{client_id}',
    )
    if data is not None:
        print(f'✅ Cliente {client_id} cancelado')
        return True
    print(f'❌ Falha ao cancelar cliente {client_id}')
    return False
