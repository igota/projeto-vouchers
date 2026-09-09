import re
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def _extrair_view_state(html):
    m = (re.search(r'name="javax\.faces\.ViewState"\s+id="javax\.faces\.ViewState"\s+value="([^"]*)"', html)
         or re.search(r'javax\.faces\.ViewState[^>]*value="([^"]*)"', html))
    return m.group(1) if m else None

def _logado_com_sucesso(html):
    return 'iconmenuPrincipal' in html and 'funcaoclickForm:login' not in html

def login_vitae(vitae_url, username, password):
    """Valida credenciais no Vitae via HTTP puro. Retorna {'sucesso': bool, 'erro': str|None}."""
    login_url = f'{vitae_url}/seguranca/login.jsf'
    session = requests.Session()
    session.headers['User-Agent'] = (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    )

    try:
        get_resp = session.get(login_url, timeout=15)
        view_state = _extrair_view_state(get_resp.text)

        if not view_state:
            return {'sucesso': False, 'erro': 'ViewState não encontrado na página do Vitae'}

        form = {
            'funcaoclickForm': 'funcaoclickForm',
            'funcaoclickForm:login': username.upper(),
            'funcaoclickForm:funcaoclick': password.upper(),
            'funcaoclickForm:logar': 'Confirmar',
            'javax.faces.ViewState': view_state,
        }

        post_resp = session.post(login_url, data=form, headers={
            'Content-Type': 'application/x-www-form-urlencoded',
            'Referer': login_url,
            'Origin': vitae_url,
        }, timeout=15)

        if not _logado_com_sucesso(post_resp.text):
            return {'sucesso': False, 'erro': 'Usuário ou Senha do Vitae incorretos!'}

        return {'sucesso': True}

    except Exception as e:
        return {'sucesso': False, 'erro': str(e)}
