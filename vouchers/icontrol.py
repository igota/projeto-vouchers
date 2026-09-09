# busca_completa.py
import os
import unicodedata
import requests
import urllib3
from dotenv import load_dotenv
from typing import Optional, List, Dict, Any

load_dotenv()
urllib3.disable_warnings()


def _remover_acentos(texto: str) -> str:
    """Remove acentos/cedilha (NFKD + descarta marcas combinantes).

    O iControl (endereço em ICONTROL_BASE_URL, ver .env) faz a busca por nome no servidor dele e
    a comparação lá é sensível a acento — "Graças" não bate com um cadastro
    salvo como "Gracas". Normalizamos o termo digitado antes de mandar pra
    cobrir cadastros antigos/mal digitados sem acento (o caso mais comum).
    """
    nfkd = unicodedata.normalize('NFKD', texto)
    return ''.join(c for c in nfkd if not unicodedata.combining(c))

class BuscaCredencial:
    def __init__(self):
        self.session = requests.Session()
        self.session.verify = False
        self.base_url = os.environ['ICONTROL_BASE_URL']
        self.logado = False
    
    def login(self) -> bool:
        """Realiza login no sistema"""
        print("🔐 Fazendo login...")
        
        login_data = {'Login': os.environ['ICONTROL_USERNAME'], 'Senha': os.environ['ICONTROL_PASSWORD']}
        
        try:
            response = self.session.post(
                f'{self.base_url}/usuariosistema/login',
                data=login_data,
                allow_redirects=False
            )
            
            if response.status_code == 302:
                self.logado = True
                print("✅ Login realizado com sucesso!")
                return True
            else:
                print(f"❌ Falha no login. Status: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ Erro no login: {e}")
            return False
    
    def buscar_por_cartao(self, numero_cartao: str) -> List[Dict[str, Any]]:
        """Busca pessoas pelo número do cartão (coluna 3)"""
        print(f"🔍 Buscando cartão: {numero_cartao}")
        form = self._montar_form_base()
        form['columns[3][search][value]'] = numero_cartao
        return self._executar_busca(form)
    
    def buscar_por_identificador(self, identificador: str) -> List[Dict[str, Any]]:
        """Busca pessoas pelo identificador (coluna 5)"""
        print(f"🔍 Buscando identificador: {identificador}")

        form = self._montar_form_base()
        form['columns[5][search][value]'] = identificador

        return self._executar_busca(form)
        
    def _montar_form_base(self) -> dict:
        colunas = [
            {'data': 'IdCredencial',     'name': '',                'searchable': 'false', 'orderable': 'false'},
            {'data': 'TipoCredencial',   'name': 'TipoCredencial',  'searchable': 'true',  'orderable': 'true'},
            {'data': 'Nome',             'name': 'Nome',            'searchable': 'true',  'orderable': 'true'},
            {'data': 'NumeroCartao',     'name': 'NumeroCartao',    'searchable': 'true',  'orderable': 'true'},
            {'data': 'CodigoInstalacao', 'name': 'CodigoInstalacao','searchable': 'true',  'orderable': 'true'},
            {'data': 'Identificador',    'name': 'Identificador',   'searchable': 'true',  'orderable': 'true'},
            {'data': 'TipoUsuario',      'name': 'TipoUsuario',     'searchable': 'true',  'orderable': 'true'},
            {'data': 'IdCredencial',     'name': '',                'searchable': 'false', 'orderable': 'false'},
        ]
        form: dict = {
            'draw': 1, 'start': 0, 'length': 50,
            'search[value]': '', 'search[regex]': 'false',
            'order[0][column]': 2, 'order[0][dir]': 'asc',
        }
        for i, col in enumerate(colunas):
            form[f'columns[{i}][data]']            = col['data']
            form[f'columns[{i}][name]']            = col['name']
            form[f'columns[{i}][searchable]']      = col['searchable']
            form[f'columns[{i}][orderable]']       = col['orderable']
            form[f'columns[{i}][search][value]']   = ''
            form[f'columns[{i}][search][regex]']   = 'false'
        return form

    def _executar_busca(self, form_data: dict) -> List[Dict[str, Any]]:
        if not self.logado:
            if not self.login():
                return []
        headers = {
            'X-Requested-With': 'XMLHttpRequest',
            'Referer': f'{self.base_url}/credencial',
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        }
        try:
            response = self.session.post(f'{self.base_url}/credencial', data=form_data, headers=headers)
            if response.status_code != 200:
                return []
            data = response.json()
            resultados = []
            for p in data.get('data') or []:
                resultados.append({
                    'id_credencial':     p.get('IdCredencial'),
                    'tipo_credencial':   p.get('TipoCredencial'),
                    'nome':              p.get('Nome'),
                    'numero_cartao':     p.get('NumeroCartao'),
                    'codigo_instalacao': p.get('CodigoInstalacao'),
                    'identificador':     p.get('Identificador'),
                    'tipo_usuario':      p.get('TipoUsuario'),
                    'email':             p.get('Email'),
                    'telefone':          p.get('Telefone'),
                    'status':            p.get('Status'),
                    'data_expiracao':    p.get('DataExpiracao'),
                })
            print(f"✅ Encontrado(s) {len(resultados)} registro(s)")
            return resultados
        except Exception as e:
            print(f"❌ Erro na requisição: {e}")
            return []

    def buscar_por_nome(self, nome: str) -> List[Dict[str, Any]]:
        """Busca pessoas pelo nome (coluna 2)"""
        nome_sem_acento = _remover_acentos(nome)
        print(f"🔍 Buscando nome: {nome} (sem acento: {nome_sem_acento})")
        form = self._montar_form_base()
        form['columns[2][search][value]'] = nome_sem_acento
        return self._executar_busca(form)

    def buscar_primeiro(self, numero_cartao: str) -> Optional[Dict[str, Any]]:
        """Retorna apenas o primeiro resultado encontrado"""
        resultados = self.buscar_por_cartao(numero_cartao)
        return resultados[0] if resultados else None


def formatar_resposta_completa(pessoa: Dict[str, Any]) -> str:
    """Formata a resposta de forma organizada"""
    if not pessoa:
        return "❌ Pessoa não encontrada"
    
    linhas = [
        "✅ PESSOA ENCONTRADA",
        "=" * 40,
        "",
        "📋 INFORMAÇÕES PESSOAIS:",
        f"   👤 Nome: {pessoa.get('nome', 'N/A')}",
        f"   🏷️ Tipo de Usuário: {pessoa.get('tipo_usuario', 'N/A')}",
        f"   🔖 Tipo de Credencial: {pessoa.get('tipo_credencial', 'N/A')}",
        "",
        "💳 DADOS DO CARTÃO:",
        f"   🔢 Número: {pessoa.get('numero_cartao', 'N/A')}",
        f"   🆔 ID Credencial: {pessoa.get('id_credencial', 'N/A')}",
        "",
        "📍 DADOS DE INSTALAÇÃO:",
        f"   📍 Código: {pessoa.get('codigo_instalacao', 'N/A')}",
        f"   🔑 Identificador: {pessoa.get('identificador', 'N/A')}",
    ]
    
    # Adiciona campos opcionais se existirem
    if pessoa.get('email'):
        linhas.extend(["", "📧 CONTATO:", f"   ✉️ Email: {pessoa['email']}"])
    
    if pessoa.get('telefone'):
        if 'CONTATO' not in str(linhas[-1]):
            linhas.extend(["", "📧 CONTATO:"])
        linhas.append(f"   📞 Telefone: {pessoa['telefone']}")
    
    if pessoa.get('status'):
        linhas.extend(["", "📊 STATUS:", f"   📌 Status: {pessoa['status']}"])
    
    if pessoa.get('data_cadastro'):
        linhas.append(f"   📅 Data Cadastro: {pessoa['data_cadastro']}")
    
    if pessoa.get('data_expiracao'):
        linhas.append(f"   ⏰ Data Expiração: {pessoa['data_expiracao']}")
    
    return '\n'.join(linhas)


# Função principal simplificada
def buscar_pessoa(numero_cartao: str) -> Dict[str, Any]:
    """Função principal para buscar pessoa pelo cartão"""
    busca = BuscaCredencial()
    resultado = busca.buscar_primeiro(numero_cartao)
    
    if resultado:
        return {'encontrado': True, **resultado}
    else:
        return {'encontrado': False, 'mensagem': 'Cartão não encontrado'}


# Teste
if __name__ == '__main__':
    import sys
    
    cartao = sys.argv[1] if len(sys.argv) > 1 else '186378290'
    
    print("🚀 SISTEMA DE BUSCA POR CARTÃO")
    print("==============================\n")
    
    resultado = buscar_pessoa(cartao)
    
    if resultado['encontrado']:
        print(formatar_resposta_completa(resultado))
    else:
        print(f"❌ {resultado['mensagem']}")