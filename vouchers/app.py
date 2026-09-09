# app.py
import os
from functools import wraps
from dotenv import load_dotenv
from flask import Flask, request, jsonify
from flask_cors import CORS
from icontrol import BuscaCredencial
from conexao import get_db_connection
from omada import buscar_cliente_por_voucher, cancelar_cliente, login_omada
from datetime import datetime
import urllib3
from typing import Optional, Dict
import socket

load_dotenv()

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)

ALLOWED_ORIGINS = [o.strip() for o in os.environ.get('ALLOWED_ORIGINS', '').split(',') if o.strip()]
CORS(app, origins=ALLOWED_ORIGINS or None)

KIOSK_API_KEY = os.environ['KIOSK_API_KEY']

TIPOS_USUARIO_PERMITIDOS = [
    t.strip().upper()
    for t in os.environ.get('TIPOS_USUARIO_PERMITIDO', 'TÉCNICO EM INFORMÁTICA').split(',')
    if t.strip()
]

IMPRESSORA_REDE_HABILITADA = os.environ.get('IMPRESSORA_REDE_HABILITADA', 'false').lower() == 'true'
IMPRESSORA_REDE_IP = os.environ.get('IMPRESSORA_REDE_IP', '')

ESTOQUE_LIMITE_MAXIMO = int(os.environ.get('ESTOQUE_LIMITE_MAXIMO', 10))
ESTOQUE_LIMITE_MINIMO = int(os.environ.get('ESTOQUE_LIMITE_MINIMO', 5))
VOUCHER_REPOSICAO_DURACAO_MINUTOS = int(os.environ.get('VOUCHER_REPOSICAO_DURACAO_MINUTOS', 1440))


def tipo_usuario_permitido(tipo_usuario_raw: str) -> Optional[str]:
    """Retorna o tipo configurado que bate com o valor cru vindo do iControl, ou None."""
    return next((t for t in TIPOS_USUARIO_PERMITIDOS if t in tipo_usuario_raw), None)


def kiosk_key_obrigatoria(f):
    """Exige o header X-Kiosk-Key nas chamadas HTTP do totem.

    Os jobs de reposição/limpeza (systemd timers, ver deploy/systemd/)
    chamam essas mesmas rotas por HTTP com a chave, então não precisam
    de um caminho de bypass aqui.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        if request.headers.get('X-Kiosk-Key') != KIOSK_API_KEY:
            return jsonify({'sucesso': False, 'mensagem': 'Não autorizado'}), 401
        return f(*args, **kwargs)
    return decorated


from gerencia import gerencia_bp
app.register_blueprint(gerencia_bp)

busca = BuscaCredencial()


# =====================================================
# IMPRESSÃO NA GODEX BPE300 (ETIQUETA 60x20mm)
# =====================================================

def quebrar_texto(texto: str, limite: int = 15) -> list:
    """Divide o texto em linhas de no máximo 'limite' caracteres"""
    if len(texto) <= limite:
        return [texto]
    
    palavras = texto.split()
    linhas = []
    linha_atual = ""
    
    for palavra in palavras:
        if len(linha_atual) + len(palavra) + 1 <= limite:
            if linha_atual:
                linha_atual += " " + palavra
            else:
                linha_atual = palavra
        else:
            if linha_atual:
                linhas.append(linha_atual)
            linha_atual = palavra
    
    if linha_atual:
        linhas.append(linha_atual)
    
    return linhas

def imprimir_etiqueta_godex(ip_impressora: str, voucher_code: str, nome_usuario: str) -> bool:
    """Envia comando EPL para Godex BPE300 (etiqueta 60x20mm) com quebra de linha"""
    try:
        # Quebrar nome em até 2 linhas
        linhas_nome = quebrar_texto(nome_usuario, limite=30)
        
        # Montar texto EPL dinamicamente
        epl = f"""
N
q609
Q203
A200,30,0,2,1,1,N,"HRN Wi-Fi VOUCHER"
A200,60,0,5,1,1,N,"{voucher_code}"
"""
        
        # Adicionar linhas do nome
        y_pos = 120
        for linha in linhas_nome:
            epl += f'A150,{y_pos},0,2,1,1,N,"{linha}"\n'
            y_pos += 20  # Espaçamento entre linhas
        
        # Restante das informações
        epl += f"""
A200,{y_pos + 30},0,2,1,1,N,"Validade: 24 horas"

P1
"""
        
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(15)
        sock.connect((ip_impressora, 9100))
        sock.send(epl.encode('utf-8'))
        sock.close()
        
        print(f"✅ Etiqueta enviada para Godex")
        return True
        
    except Exception as e:
        print(f"❌ Erro na impressão: {e}")
        return False

@app.route('/api/imprimir-etiqueta', methods=['POST'])
@kiosk_key_obrigatoria
def imprimir_etiqueta():
    """Endpoint para imprimir etiqueta na Godex BPE300"""
    try:
        if not IMPRESSORA_REDE_HABILITADA:
            return jsonify({'sucesso': False, 'mensagem': 'Impressão em rede desabilitada nas configurações.'}), 403

        dados = request.get_json()
        voucher_code = dados.get('voucher_code')
        ip_impressora = dados.get('ip_impressora') or IMPRESSORA_REDE_IP

        if not voucher_code:
            return jsonify({'sucesso': False, 'mensagem': 'Código do voucher não informado'}), 400

        if not ip_impressora:
            return jsonify({'sucesso': False, 'mensagem': 'IP da impressora não informado'}), 400

        # Buscar dados do usuário
        connection = get_db_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT vi.nome_completo, vi.tipo_usuario
                    FROM vouchers_impressos vi
                    JOIN vouchers_disponiveis vd ON vi.voucher_id = vd.id
                    WHERE vd.numero_voucher = %s
                    ORDER BY vi.data_impressao DESC
                    LIMIT 1
                """, (voucher_code,))
                usuario = cursor.fetchone()
        finally:
            connection.close()
        
        if not usuario:
            return jsonify({'sucesso': False, 'mensagem': 'Voucher não encontrado'}), 404
        
        # Enviar impressão
        sucesso = imprimir_etiqueta_godex(
            ip_impressora=ip_impressora,
            voucher_code=voucher_code,
            nome_usuario=usuario.get('nome_completo')
        )
        
        return jsonify({
            'sucesso': sucesso,
            'mensagem': 'Etiqueta enviada com sucesso' if sucesso else 'Falha na impressão'
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'sucesso': False, 'erro': str(e)}), 500



# =====================================================
# ROTA PRINCIPAL - BUSCAR USUÁRIO
# =====================================================

@app.route('/api/buscar-cartao', methods=['POST'])
@kiosk_key_obrigatoria
def buscar_cartao():
    """Busca usuário pelo número do cartão RFID"""
    try:
        dados = request.get_json()
        numero_cartao = dados.get('numero_cartao', '').strip()
        
        if not numero_cartao:
            return jsonify({
                'encontrado': False,
                'mensagem': 'Número do cartão não informado'
            }), 400
        
        if not busca.logado:
            busca.login()
        
        resultado = busca.buscar_primeiro(numero_cartao)
        
        if resultado:
            tipo_usuario_raw = resultado.get('tipo_usuario', '').upper()
            print(f"🔍 Tipo de usuário (raw): '{tipo_usuario_raw}'")
            
            # Determinar tipo para exibição
            tipo_permitido = tipo_usuario_permitido(tipo_usuario_raw)
            if tipo_permitido:
                tipo_exibicao = tipo_permitido
                tipo_normalizado = tipo_permitido

            else:
                return jsonify({
                    'encontrado': False,
                    'mensagem': f'Acesso não autorizado. Tipo: {tipo_usuario_raw}'
                }), 403
            
            return jsonify({
                'encontrado': True,
                'usuario': {
                    'id': resultado.get('id_credencial'),
                    'nome': resultado.get('nome'),
                    'tipo_usuario': tipo_normalizado,
                    'tipo_usuario_exibicao': tipo_exibicao,  # ← NOVO CAMPO
                    'tipo_credencial': resultado.get('tipo_credencial'),
                    'numero_cartao': resultado.get('numero_cartao'),
                    'codigo_instalacao': resultado.get('codigo_instalacao'),
                    'identificador': resultado.get('identificador'),
                    'email': resultado.get('email'),
                    'telefone': resultado.get('telefone'),
                    'status': resultado.get('status'),
                    'data_expiracao': resultado.get('data_expiracao')
                }
            })
        else:
            return jsonify({
                'encontrado': False,
                'mensagem': 'Cartão não encontrado no sistema'
            })
            
    except Exception as e:
        return jsonify({
            'encontrado': False,
            'mensagem': f'Erro na busca: {str(e)}'
        }), 500

# =====================================================
# ROTA DE CANCELAMENTO DE VOUCHER
# =====================================================

@app.route('/api/cancelar-voucher', methods=['POST'])
@kiosk_key_obrigatoria
def cancelar_voucher():
    """Cancela um voucher ativo do usuário (apenas no Omada)"""
    try:
        dados = request.get_json()
        voucher_code = dados.get('voucher_code')
        
        if not voucher_code:
            return jsonify({
                'sucesso': False,
                'mensagem': 'Código do voucher não informado'
            }), 400
        
        client_id = buscar_cliente_por_voucher(voucher_code)
        
        if not client_id:
            return jsonify({
                'sucesso': False,
                'mensagem': 'Voucher não encontrado ou já está inativo'
            }), 404
        
        sucesso = cancelar_cliente(client_id)
        
        return jsonify({
            'sucesso': sucesso,
            'mensagem': 'Voucher cancelado com sucesso' if sucesso else 'Erro ao cancelar voucher'
        })
        
    except Exception as e:
        return jsonify({'sucesso': False, 'erro': str(e)}), 500


# =====================================================
# ROTA DE VERIFICAÇÃO DE ESTOQUE
# =====================================================

@app.route('/api/verificar-estoque', methods=['GET'])
@kiosk_key_obrigatoria
def verificar_estoque():
    """Verifica o estoque atual de vouchers de 1 dia"""
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT COUNT(*) as total,
                       SUM(CASE WHEN status = 'disponivel' THEN 1 ELSE 0 END) as disponiveis,
                       SUM(CASE WHEN status = 'usado' THEN 1 ELSE 0 END) as usados
                FROM vouchers_disponiveis 
                WHERE periodo = '1dia'
            """)
            result = cursor.fetchone()
            
            return jsonify({
                'sucesso': True,
                'estoque': {
                    'periodo': '1dia',
                    'total': result['total'],
                    'disponiveis': result['disponiveis'],
                    'usados': result['usados']
                }
            })
    except Exception as e:
        return jsonify({'sucesso': False, 'erro': str(e)}), 500
    finally:
        connection.close()


# =====================================================
# ROTA DE REPOSIÇÃO AUTOMÁTICA
# =====================================================

@app.route('/api/repor-estoque', methods=['POST'])
@kiosk_key_obrigatoria
def repor_estoque():
    """Verifica estoque e repõe se necessário (limites configurados via .env)"""
    LIMITE_MAXIMO = ESTOQUE_LIMITE_MAXIMO
    LIMITE_MINIMO = ESTOQUE_LIMITE_MINIMO

    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT COUNT(*) as disponiveis
                FROM vouchers_disponiveis 
                WHERE periodo = '1dia' AND status = 'disponivel'
            """)
            result = cursor.fetchone()
            disponivel = result['disponiveis'] if result else 0
            
            if disponivel > LIMITE_MINIMO:
                return jsonify({
                    'sucesso': True,
                    'reposto': False,
                    'mensagem': f'Estoque OK. {disponivel} vouchers disponíveis'
                })
            
            falta = LIMITE_MAXIMO - disponivel
            print(f"⚠️ Estoque baixo: {disponivel} disponíveis. Repondo +{falta}")
            
            from voucherService import gerar_e_inserir_vouchers
            
            sucesso = gerar_e_inserir_vouchers(
                quantidade=falta, max_workers=3, delay=0.3,
                duracao_minutos=VOUCHER_REPOSICAO_DURACAO_MINUTOS,
            )
            
            return jsonify({
                'sucesso': sucesso,
                'reposto': sucesso,
                'quantidade_reposta': falta,
                'mensagem': f'Estoque reposto com {falta} vouchers' if sucesso else 'Falha na reposição'
            })
            
    except Exception as e:
        return jsonify({'sucesso': False, 'erro': str(e)}), 500
    finally:
        connection.close()


# =====================================================
# ROTA DE LIBERAÇÃO DE VOUCHER (COMPLETA)
# =====================================================

@app.route('/api/liberar-voucher', methods=['POST'])
@kiosk_key_obrigatoria
def liberar_voucher():
    """Fluxo completo: busca usuário, verifica voucher ativo e gera novo de 1 dia"""
    try:
        dados = request.get_json()
        numero_cartao = dados.get('numero_cartao')
        
        if not numero_cartao:
            return jsonify({'sucesso': False, 'mensagem': 'Cartão não informado'}), 400
        
        if not busca.logado:
            busca.login()
        
        usuario = busca.buscar_primeiro(numero_cartao)
        
        if not usuario:
            return jsonify({'sucesso': False, 'mensagem': 'Cartão não encontrado no sistema'}), 404
        
        nome_usuario = usuario.get('nome')
        id_credencial = usuario.get('id_credencial')
        tipo_usuario_raw = usuario.get('tipo_usuario', '').upper()
        print(f"🔍 Tipo de usuário (raw): '{tipo_usuario_raw}'")
        print(f"🔍 ID Credencial: {id_credencial}")
        
        # Validar e definir tipo de exibição
        tipo_permitido = tipo_usuario_permitido(tipo_usuario_raw)
        if tipo_permitido:
            tipo_exibicao = tipo_permitido
        else:
            return jsonify({
                'sucesso': False,
                'mensagem': f'Acesso não autorizado. Tipo: {tipo_usuario_raw}'
            }), 403
        
        periodo = '1dia'
        
        connection = get_db_connection()
        
        try:
            with connection.cursor() as cursor:
                # ============================================
                # VERIFICAR SE JÁ EXISTE IMPRESSÃO
                # PRIORIDADE: id_credencial (mais confiável)
                # ============================================
                
                # 1. Buscar por id_credencial (prioritário)
                cursor.execute("""
                    SELECT vi.*, vd.numero_voucher 
                    FROM vouchers_impressos vi
                    JOIN vouchers_disponiveis vd ON vi.voucher_id = vd.id
                    WHERE vi.id_credencial = %s
                    ORDER BY vi.data_impressao DESC
                    LIMIT 1
                """, (id_credencial,))
                
                registro_existente = cursor.fetchone()
                
                # 2. Fallback: buscar por nome (se não encontrou por id_credencial)
                if not registro_existente:
                    print(f"🔍 Não encontrado por id_credencial, buscando por nome...")
                    cursor.execute("""
                        SELECT vi.*, vd.numero_voucher 
                        FROM vouchers_impressos vi
                        JOIN vouchers_disponiveis vd ON vi.voucher_id = vd.id
                        WHERE vi.nome_completo = %s
                        ORDER BY vi.data_impressao DESC
                        LIMIT 1
                    """, (nome_usuario,))
                    registro_existente = cursor.fetchone()
                
                if registro_existente:
                    voucher_code_existente = registro_existente['numero_voucher']
                    client = buscar_cliente_por_voucher(voucher_code_existente)
                    
                    if not client:
                        # Voucher NÃO está no Omada (nunca foi usado)
                        return jsonify({
                            'sucesso': False,
                            'voucher_nao_utilizado': True,
                            'voucher_code': voucher_code_existente,
                            'mensagem': f'Você possui um voucher que ainda não foi utilizado: {voucher_code_existente}'
                        }), 410
                    
                    if client.get('valid'):
                        # Voucher ativo
                        return jsonify({
                            'sucesso': False,
                            'requer_confirmacao': True,
                            'voucher_ativo': voucher_code_existente,
                            'mensagem': f'Você já possui um voucher ativo. Deseja cancelá-lo e gerar um novo?'
                        }), 409
                    else:
                        # Voucher inativo (valid = false)
                        print(f"ℹ️ Voucher {voucher_code_existente} inativo. Gerando novo...")
                
                # ============================================
                # BUSCAR VOUCHER DISPONÍVEL NO ESTOQUE
                # ============================================
                cursor.execute("""
                    SELECT id, numero_voucher 
                    FROM vouchers_disponiveis 
                    WHERE periodo = '1dia' AND status = 'disponivel'
                    LIMIT 1
                """)
                
                voucher = cursor.fetchone()
                
                if not voucher:
                    return jsonify({'sucesso': False, 'mensagem': 'Estoque vazio. Contate o administrador.'}), 404
                
                # Marcar voucher como usado
                cursor.execute("""
                    UPDATE vouchers_disponiveis 
                    SET status = 'usado' 
                    WHERE id = %s
                """, (voucher['id'],))
                
                # ============================================
                # REGISTRAR IMPRESSÃO (COM id_credencial)
                # ============================================
                if registro_existente:
                    # Atualizar registro existente
                    cursor.execute("""
                        UPDATE vouchers_impressos 
                        SET voucher_id = %s, data_impressao = %s
                        WHERE id = %s
                    """, (voucher['id'], datetime.now(), registro_existente['id']))
                else:
                    # Inserir novo registro com id_credencial
                    cursor.execute("""
                        INSERT INTO vouchers_impressos 
                        (voucher_id, numero_cartao, nome_completo, tipo_usuario, data_impressao, id_credencial)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, (voucher['id'], numero_cartao, nome_usuario, tipo_exibicao, datetime.now(), id_credencial))
                
                connection.commit()
                
                return jsonify({
                    'sucesso': True,
                    'voucher_code': voucher['numero_voucher'],
                    'nome_usuario': nome_usuario,
                    'tipo_usuario': tipo_exibicao,
                    'periodo': '1dia',
                    'mensagem': 'Voucher liberado com sucesso!'
                })
                
        except Exception as e:
            connection.rollback()
            import traceback
            traceback.print_exc()
            return jsonify({'sucesso': False, 'erro': str(e)}), 500
        finally:
            connection.close()
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'sucesso': False, 'erro': str(e)}), 500


# =====================================================
# ROTA PARA CONFIRMAR SUBSTITUIÇÃO DE VOUCHER
# =====================================================

@app.route('/api/substituir-voucher', methods=['POST'])
@kiosk_key_obrigatoria
def substituir_voucher():
    """Cancela o voucher ativo e gera um novo"""
    try:
        dados = request.get_json()
        numero_cartao = dados.get('numero_cartao')
        voucher_antigo = dados.get('voucher_antigo')
        
        if not numero_cartao or not voucher_antigo:
            return jsonify({'sucesso': False, 'mensagem': 'Dados incompletos'}), 400
        
        # Cancelar voucher antigo no Omada
        client = buscar_cliente_por_voucher(voucher_antigo)
        if client and client.get('valid'):
            cancelar_cliente(client.get('id'))
        
        # Buscar usuário no iControl
        if not busca.logado:
            busca.login()
        
        usuario = busca.buscar_primeiro(numero_cartao)
        
        if not usuario:
            return jsonify({'sucesso': False, 'mensagem': 'Usuário não encontrado'}), 404
        
        nome_usuario = usuario.get('nome')
        id_credencial = usuario.get('id_credencial')
        tipo_usuario = usuario.get('tipo_usuario', '').upper()
        
        print(f"🔍 Substituindo voucher para: {nome_usuario} (ID: {id_credencial})")
        
        connection = get_db_connection()
        
        try:
            with connection.cursor() as cursor:
                # Buscar voucher disponível no estoque
                cursor.execute("""
                    SELECT id, numero_voucher 
                    FROM vouchers_disponiveis 
                    WHERE periodo = '1dia' AND status = 'disponivel'
                    LIMIT 1
                """)
                
                voucher = cursor.fetchone()
                
                if not voucher:
                    return jsonify({'sucesso': False, 'mensagem': 'Estoque vazio'}), 404
                
                # Marcar voucher como usado
                cursor.execute("""
                    UPDATE vouchers_disponiveis 
                    SET status = 'usado' 
                    WHERE id = %s
                """, (voucher['id'],))
                
                # ============================================
                # ATUALIZAR REGISTRO COM id_credencial
                # ============================================
                cursor.execute("""
                    UPDATE vouchers_impressos 
                    SET voucher_id = %s, data_impressao = %s
                    WHERE id_credencial = %s
                """, (voucher['id'], datetime.now(), id_credencial))
                
                connection.commit()
                
                return jsonify({
                    'sucesso': True,
                    'voucher_code': voucher['numero_voucher'],
                    'nome_usuario': nome_usuario,
                    'tipo_usuario': tipo_usuario,
                    'periodo': '1dia',
                    'mensagem': 'Voucher substituído com sucesso!'
                })
                
        except Exception as e:
            connection.rollback()
            import traceback
            traceback.print_exc()
            return jsonify({'sucesso': False, 'erro': str(e)}), 500
        finally:
            connection.close()
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'sucesso': False, 'erro': str(e)}), 500

# =====================================================
# ROTA DE LIMPEZA DE EXPIrados
# =====================================================

@app.route('/api/limpar-expirados', methods=['POST'])
@kiosk_key_obrigatoria
def limpar_expirados():
    print("="*50)
    print("🔍 [LIMPAR] FUNÇÃO LIMPAR EXECUTADA - NÃO DEVE GERAR VOUCHERS")
    print("="*50)
    """Remove registros do banco quando valid = false no Omada"""
    try:
        # Usar a função do omada.py
        from omada import login_omada, buscar_cliente_por_voucher
        
        if not login_omada():
            return jsonify({'sucesso': False, 'mensagem': 'Falha no login Omada'}), 500
        
        connection = get_db_connection()
        removidos = 0
        verificados = 0
        
        try:
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT vi.id, vd.numero_voucher 
                    FROM vouchers_impressos vi
                    JOIN vouchers_disponiveis vd ON vi.voucher_id = vd.id
                """)
                
                registros = cursor.fetchall()
                
                for registro in registros:
                    voucher_id = registro['id']
                    voucher_code = registro['numero_voucher']
                    verificados += 1
                    
                    # Usar a função do omada.py
                    client = buscar_cliente_por_voucher(voucher_code)
                    
                    if client and client.get('valid') == False:
                        cursor.execute("DELETE FROM vouchers_impressos WHERE id = %s", (voucher_id,))
                        removidos += 1
                        print(f"[LIMPEZA] Removido: {voucher_code} (valid=false)")
                
                connection.commit()
                
                return jsonify({
                    'sucesso': True,
                    'mensagem': f'{removidos} registros removidos de {verificados} verificados'
                })
                
        finally:
            connection.close()
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'sucesso': False, 'erro': str(e)}), 500


# =====================================================
# INICIALIZAÇÃO (dev)
#
# Em produção quem sobe este app é o Gunicorn (ver gunicorn_conf.py),
# que importa `app` diretamente e nunca executa este bloco. Os jobs de
# reposição de estoque e limpeza de expirados rodam via systemd timers
# batendo em /api/repor-estoque e /api/limpar-expirados (ver deploy/systemd/).
# =====================================================

if __name__ == '__main__':
    print("🚀 Servidor rodando em http://localhost:5000")
    print("\n📋 Endpoints disponíveis:")
    print("   POST /api/buscar-cartao - Busca usuário (apenas ACOMPANHANTE)")
    print("   POST /api/cancelar-voucher - Cancela voucher ativo")
    print("   GET  /api/verificar-estoque - Verifica estoque")
    print("   POST /api/repor-estoque - Repõe estoque se necessário")
    print("   POST /api/liberar-voucher - Libera voucher (fluxo completo)")
    print("   POST /api/substituir-voucher - Substitui voucher ativo")
    print("   POST /api/limpar-expirados - Remove vouchers expirados")
    print("   POST /api/imprimir-etiqueta - Imprime etiqueta na impressora de rede")

    debug_mode = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    app.run(debug=debug_mode, use_reloader=False, host='0.0.0.0', port=5000)