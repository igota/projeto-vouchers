import json
import os
import secrets
from datetime import datetime, timedelta
from functools import wraps
from flask import Blueprint, request, jsonify

from conexao import get_db_connection
from vitae_auth import login_vitae

VITAE_URL = os.environ['VITAE_URL']
USUARIOS_FILE = os.path.join(os.path.dirname(__file__), 'json', 'usuarios_permitidos.json')

gerencia_bp = Blueprint('gerencia', __name__, url_prefix='/gerencia')

# Sessões na tabela gerencia_sessoes (não em memória): o Gunicorn roda vários
# workers/processos, e um dict em memória de processo fica invisível pros
# outros — quem logasse num worker aparecia como "Não autenticado" nos
# outros. A tabela é compartilhada por todos.
SESSION_DURATION = timedelta(hours=2)


def _carregar_usuarios_permitidos():
    with open(USUARIOS_FILE, 'r', encoding='utf-8') as f:
        return [u.upper() for u in json.load(f)['usuarios']]


def _criar_sessao(username: str) -> str:
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now() + SESSION_DURATION
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM gerencia_sessoes WHERE expires_at < NOW()")
            cursor.execute(
                "INSERT INTO gerencia_sessoes (token, username, expires_at) VALUES (%s, %s, %s)",
                (token, username, expires_at),
            )
        connection.commit()
    finally:
        connection.close()
    return token


def _remover_sessao(token: str):
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM gerencia_sessoes WHERE token = %s", (token,))
        connection.commit()
    finally:
        connection.close()


def _verificar_token(token: str | None):
    if not token:
        return None
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT username, expires_at FROM gerencia_sessoes WHERE token = %s",
                (token,),
            )
            sessao = cursor.fetchone()
    finally:
        connection.close()

    if not sessao:
        return None
    if datetime.now() > sessao['expires_at']:
        _remover_sessao(token)
        return None
    return {'username': sessao['username'], 'expires': sessao['expires_at']}


def login_obrigatorio(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        sessao = _verificar_token(request.headers.get('X-Gerencia-Token'))
        if not sessao:
            return jsonify({'erro': 'Não autenticado'}), 401
        request.gerencia_username = sessao['username']
        return f(*args, **kwargs)
    return decorated


# =====================================================
# AUTH
# =====================================================

@gerencia_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json() or {}
    username = (data.get('username') or '').strip().upper()
    password = (data.get('password') or '').strip()

    if not username or not password:
        return jsonify({'success': False, 'error': 'Usuário e Senha são obrigatórios!'})

    if username not in _carregar_usuarios_permitidos():
        return jsonify({'success': False, 'error': 'Usuário não autorizado a usar este sistema.'})

    try:
        resultado = login_vitae(VITAE_URL, username, password)
    except Exception:
        return jsonify({'success': False, 'error': 'Erro ao validar credenciais no Vitae. Tente novamente.'})

    if not resultado['sucesso']:
        return jsonify({'success': False, 'error': 'Usuário ou Senha do Vitae incorretos!'})

    token = _criar_sessao(username)

    return jsonify({'success': True, 'token': token, 'username': username})


@gerencia_bp.route('/logout', methods=['POST'])
def logout():
    token = request.headers.get('X-Gerencia-Token')
    if token:
        _remover_sessao(token)
    return jsonify({'success': True})


# =====================================================
# API DE DADOS (protegida por token)
# =====================================================

@gerencia_bp.route('/api/buscar-usuario', methods=['POST'])
@login_obrigatorio
def api_buscar_usuario():
    from icontrol import BuscaCredencial
    data = request.get_json() or {}
    tipo = data.get('tipo', '')   # 'nome' ou 'cartao'
    valor = (data.get('valor') or '').strip()

    if not valor:
        return jsonify({'sucesso': False, 'erro': 'Informe o valor para busca.'}), 400

    busca = BuscaCredencial()

    if tipo == 'nome':
        resultados = busca.buscar_por_nome(valor)
    
    elif tipo == 'identificador':
        resultados = busca.buscar_por_identificador(valor)
    else:
        return jsonify({'sucesso': False, 'erro': 'Tipo de busca inválido.'}), 400

    return jsonify({'sucesso': True, 'resultados': resultados, 'total': len(resultados)})


@gerencia_bp.route('/api/verificar-voucher', methods=['POST'])
@login_obrigatorio
def api_verificar_voucher():
    from conexao import get_db_connection
    from omada import buscar_cliente_por_voucher
    data = request.get_json() or {}
    id_credencial = data.get('id_credencial')
    numero_cartao = (data.get('numero_cartao') or '').strip()

    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            if id_credencial:
                cursor.execute("""
                    SELECT vi.data_impressao, vd.numero_voucher, vd.periodo
                    FROM vouchers_impressos vi
                    JOIN vouchers_disponiveis vd ON vi.voucher_id = vd.id
                    WHERE vi.id_credencial = %s
                    ORDER BY vi.data_impressao DESC LIMIT 1
                """, (id_credencial,))
            elif numero_cartao:
                cursor.execute("""
                    SELECT vi.data_impressao, vd.numero_voucher, vd.periodo
                    FROM vouchers_impressos vi
                    JOIN vouchers_disponiveis vd ON vi.voucher_id = vd.id
                    WHERE vi.numero_cartao = %s
                    ORDER BY vi.data_impressao DESC LIMIT 1
                """, (numero_cartao,))
            else:
                return jsonify({'sucesso': False, 'erro': 'ID ou cartão necessário.'}), 400
            reg = cursor.fetchone()
    except Exception as e:
        return jsonify({'sucesso': False, 'erro': str(e)}), 500
    finally:
        connection.close()

    # Situação 1 — sem registro no banco
    if not reg:
        return jsonify({'sucesso': True, 'situacao': 'sem_voucher'})

    voucher_code   = reg['numero_voucher']
    data_impressao = reg['data_impressao'].strftime('%d/%m/%Y %H:%M') if reg['data_impressao'] else None
    periodo        = reg.get('periodo') or ''

    # Consulta o Omada para saber se o voucher foi usado
    client = buscar_cliente_por_voucher(voucher_code)

    if not client:
        # Situação 2 — está no banco mas nunca foi utilizado (não aparece no Omada)
        return jsonify({
            'sucesso': True,
            'situacao': 'nao_utilizado',
            'voucher_code': voucher_code,
            'data_impressao': data_impressao,
            'periodo': periodo,
        })

    if client.get('valid'):
        # Situação 3 — voucher ativo no Omada
        def _fmt_ts(ms):
            if not ms:
                return None
            try:
                return datetime.fromtimestamp(int(ms) / 1000).strftime('%d/%m/%Y %H:%M')
            except Exception:
                return None

        data_inicio    = _fmt_ts(client.get('start'))
        data_expiracao = _fmt_ts(client.get('end'))

        return jsonify({
            'sucesso': True,
            'situacao': 'ativo',
            'voucher_code': voucher_code,
            'data_impressao': data_impressao,
            'periodo': periodo,
            'data_inicio': data_inicio,
            'data_expiracao': data_expiracao,
            'dispositivo': client.get('name') or '',
        })

    # Voucher expirado no Omada (valid=false) → equivale a sem voucher
    return jsonify({'sucesso': True, 'situacao': 'sem_voucher'})


def converter_para_minutos(valor: int, unidade: str) -> int:
    """Converte valor + unidade para minutos"""
    if unidade == 'Minutos':
        return valor
    elif unidade == 'Horas':
        return valor * 60
    elif unidade == 'Dias':
        return valor * 24 * 60
    else:
        return valor  # fallback


def formatar_periodo(valor: int, unidade: str) -> str:
    """Formata o período para exibição/histórico"""
    return f"{valor} {unidade}"


def montar_nota_voucher(nome: str) -> str:
    """Nota do voucher no Omada: usuário logado (gerência) + nome do funcionário.

    Sem timestamp, por pedido explícito — mas isso significa que gerar um
    voucher de novo pro mesmo funcionário pelo mesmo usuário repete a mesma
    nota. gerar_voucher_omada() localiza o voucher recém-criado filtrando
    por nota exata, então nesse caso ele pode achar um voucher antigo com a
    mesma nota em vez do que acabou de ser criado.
    """
    return f"{request.gerencia_username}+{nome}"

@gerencia_bp.route('/api/gerar-voucher', methods=['POST'])
@login_obrigatorio
def api_gerar_voucher():
    from conexao import get_db_connection
    from omada import gerar_voucher_omada

    data = request.get_json() or {}
    id_credencial = data.get('id_credencial')
    numero_cartao = (data.get('numero_cartao') or '').strip()
    nome = (data.get('nome') or '').strip()
    tipo_usuario = (data.get('tipo_usuario') or '').strip()
    duracao_valor = data.get('duracao_valor')
    duracao_unidade = data.get('duracao_unidade', 'Dias')

    # Converter duracao_valor para int
    duracao_valor = int(duracao_valor) if duracao_valor else 0

    if duracao_valor <= 0:
        return jsonify({'sucesso': False, 'mensagem': 'Informe um valor válido para o período.'}), 400

    # ... resto do código ...

    # Converter para minutos
    minutos = converter_para_minutos(duracao_valor, duracao_unidade)

    if minutos <= 0:
        return jsonify({'sucesso': False, 'mensagem': 'Período inválido.'}), 400

    # Formatar período para salvar no banco
    periodo_formatado = formatar_periodo(duracao_valor, duracao_unidade)

    # Gerar voucher no Omada com a duração escolhida
    voucher_code = gerar_voucher_omada(minutos, montar_nota_voucher(nome))

    if not voucher_code:
        return jsonify({'sucesso': False, 'mensagem': 'Erro ao gerar voucher no Omada.'}), 500

    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            # 1. Inserir no estoque com o período escolhido
            cursor.execute("""
                INSERT INTO vouchers_disponiveis 
                (numero_voucher, periodo, status, created_at)
                VALUES (%s, %s, %s, %s)
            """, (voucher_code, periodo_formatado, 'disponivel', datetime.now()))

            # 2. PEGAR O ID DO VOUCHER INSERIDO
            voucher_id = cursor.lastrowid

            # 3. Verificar se já existe impressão para este usuário
            if id_credencial:
                cursor.execute("SELECT id FROM vouchers_impressos WHERE id_credencial = %s", (id_credencial,))
            else:
                cursor.execute("SELECT id FROM vouchers_impressos WHERE numero_cartao = %s", (numero_cartao,))
            existente = cursor.fetchone()

            # 4. Registrar impressão (USANDO O voucher_id CORRETO)
            if existente:
                cursor.execute("""
                    UPDATE vouchers_impressos 
                    SET voucher_id = %s, data_impressao = %s
                    WHERE id = %s
                """, (voucher_id, datetime.now(), existente['id']))
            else:
                cursor.execute("""
                    INSERT INTO vouchers_impressos
                        (voucher_id, numero_cartao, nome_completo, tipo_usuario, data_impressao, id_credencial)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (voucher_id, numero_cartao, nome, tipo_usuario, datetime.now(), id_credencial))

            connection.commit()
            return jsonify({'sucesso': True, 'voucher_code': voucher_code})
    except Exception as e:
        connection.rollback()
        return jsonify({'sucesso': False, 'erro': str(e)}), 500
    finally:
        connection.close()


@gerencia_bp.route('/api/substituir-voucher', methods=['POST'])
@login_obrigatorio
def api_substituir_voucher():
    from conexao import get_db_connection
    from omada import buscar_cliente_por_voucher, cancelar_cliente, gerar_voucher_omada

    data = request.get_json() or {}
    voucher_antigo = (data.get('voucher_antigo') or '').strip()
    id_credencial = data.get('id_credencial')
    numero_cartao = (data.get('numero_cartao') or '').strip()
    nome = (data.get('nome') or '').strip()
    tipo_usuario = (data.get('tipo_usuario') or '').strip()
    duracao_valor = data.get('duracao_valor')
    duracao_unidade = data.get('duracao_unidade', 'Dias')

    # Converter duracao_valor para int
    duracao_valor = int(duracao_valor) if duracao_valor else 0

    if duracao_valor <= 0:
        return jsonify({'sucesso': False, 'mensagem': 'Informe um valor válido para o período.'}), 400

    minutos = converter_para_minutos(duracao_valor, duracao_unidade)
    if minutos <= 0:
        return jsonify({'sucesso': False, 'mensagem': 'Período inválido.'}), 400

    periodo_formatado = formatar_periodo(duracao_valor, duracao_unidade)

    # Cancelar voucher antigo no Omada
    client = buscar_cliente_por_voucher(voucher_antigo)
    if client and client.get('valid'):
        cancelar_cliente(client.get('id'))

    # Gerar novo voucher
    voucher_code = gerar_voucher_omada(minutos, montar_nota_voucher(nome))

    if not voucher_code:
        return jsonify({'sucesso': False, 'mensagem': 'Erro ao gerar voucher no Omada.'}), 500

    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            # 1. Inserir no estoque
            cursor.execute("""
                INSERT INTO vouchers_disponiveis 
                (numero_voucher, periodo, status, created_at)
                VALUES (%s, %s, %s, %s)
            """, (voucher_code, periodo_formatado, 'disponivel', datetime.now()))

            # 2. PEGAR O ID DO VOUCHER INSERIDO
            voucher_id = cursor.lastrowid

            # 3. Verificar se já existe impressão
            if id_credencial:
                cursor.execute("SELECT id FROM vouchers_impressos WHERE id_credencial = %s", (id_credencial,))
            else:
                cursor.execute("SELECT id FROM vouchers_impressos WHERE numero_cartao = %s", (numero_cartao,))
            existente = cursor.fetchone()

            # 4. Atualizar impressão (USANDO O voucher_id CORRETO)
            if existente:
                cursor.execute("""
                    UPDATE vouchers_impressos 
                    SET voucher_id = %s, data_impressao = %s
                    WHERE id = %s
                """, (voucher_id, datetime.now(), existente['id']))
            else:
                cursor.execute("""
                    INSERT INTO vouchers_impressos
                        (voucher_id, numero_cartao, nome_completo, tipo_usuario, data_impressao, id_credencial)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (voucher_id, numero_cartao, nome, tipo_usuario, datetime.now(), id_credencial))

            connection.commit()
            return jsonify({'sucesso': True, 'voucher_code': voucher_code})
    except Exception as e:
        connection.rollback()
        return jsonify({'sucesso': False, 'erro': str(e)}), 500
    finally:
        connection.close()

@gerencia_bp.route('/api/desativar-voucher', methods=['POST'])
@login_obrigatorio
def api_desativar_voucher():
    from conexao import get_db_connection
    from omada import buscar_cliente_por_voucher, cancelar_cliente, deletar_voucher_omada
    data = request.get_json() or {}
    id_credencial = data.get('id_credencial')
    numero_cartao = (data.get('numero_cartao') or '').strip()

    if not id_credencial and not numero_cartao:
        return jsonify({'sucesso': False, 'mensagem': 'ID ou cartão necessário.'}), 400

    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            if id_credencial:
                cursor.execute("""
                    SELECT vi.id as impressao_id, vd.numero_voucher
                    FROM vouchers_impressos vi
                    JOIN vouchers_disponiveis vd ON vi.voucher_id = vd.id
                    WHERE vi.id_credencial = %s
                    ORDER BY vi.data_impressao DESC LIMIT 1
                """, (id_credencial,))
            else:
                cursor.execute("""
                    SELECT vi.id as impressao_id, vd.numero_voucher
                    FROM vouchers_impressos vi
                    JOIN vouchers_disponiveis vd ON vi.voucher_id = vd.id
                    WHERE vi.numero_cartao = %s
                    ORDER BY vi.data_impressao DESC LIMIT 1
                """, (numero_cartao,))
            reg = cursor.fetchone()

            if not reg:
                return jsonify({'sucesso': False, 'mensagem': 'Nenhum voucher registrado para este usuário.'})

            client = buscar_cliente_por_voucher(reg['numero_voucher'])

            if client and client.get('valid'):
                sucesso = cancelar_cliente(client.get('id'))
            else:
                sucesso = deletar_voucher_omada(reg['numero_voucher'])

            if sucesso:
                cursor.execute("DELETE FROM vouchers_impressos WHERE id = %s", (reg['impressao_id'],))
                connection.commit()

            return jsonify({
                'sucesso': sucesso,
                'mensagem': 'Voucher desativado com sucesso!' if sucesso else 'Erro ao desativar voucher no Omada.',
            })

    except Exception as e:
        connection.rollback()
        return jsonify({'sucesso': False, 'erro': str(e)}), 500
    finally:
        connection.close()


@gerencia_bp.route('/api/me')
@login_obrigatorio
def me():
    return jsonify({'username': request.gerencia_username})


@gerencia_bp.route('/api/estoque')
@login_obrigatorio
def api_estoque():
    from conexao import get_db_connection
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN status = 'disponivel' THEN 1 ELSE 0 END) as disponiveis,
                    SUM(CASE WHEN status = 'usado'     THEN 1 ELSE 0 END) as usados
                FROM vouchers_disponiveis
                WHERE periodo = '1dia'
            """)
            return jsonify({'sucesso': True, 'estoque': cursor.fetchone()})
    except Exception as e:
        return jsonify({'sucesso': False, 'erro': str(e)}), 500
    finally:
        connection.close()


@gerencia_bp.route('/api/historico')
@login_obrigatorio
def api_historico():
    from conexao import get_db_connection
    pagina = int(request.args.get('pagina', 1))
    por_pagina = int(request.args.get('por_pagina', 20))
    offset = (pagina - 1) * por_pagina

    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT vi.id, vd.numero_voucher, vi.nome_completo,
                       vi.tipo_usuario, vi.numero_cartao,
                       DATE_FORMAT(vi.data_impressao, '%%d/%%m/%%Y %%H:%%i') as data_impressao
                FROM vouchers_impressos vi
                JOIN vouchers_disponiveis vd ON vi.voucher_id = vd.id
                ORDER BY vi.data_impressao DESC
                LIMIT %s OFFSET %s
            """, (por_pagina, offset))
            registros = cursor.fetchall()

            cursor.execute("SELECT COUNT(*) as total FROM vouchers_impressos")
            total = cursor.fetchone()['total']

        return jsonify({'sucesso': True, 'registros': registros, 'total': total, 'pagina': pagina})
    except Exception as e:
        return jsonify({'sucesso': False, 'erro': str(e)}), 500
    finally:
        connection.close()
