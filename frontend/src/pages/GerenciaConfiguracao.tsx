import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { gerenciaFetch, getToken } from '../gerenciaApi'
import GerenciaHeader from './GerenciaHeader'
import './GerenciaConsulta.css'
import './GerenciaConfiguracao.css'

type Tipo = 'COORDENADOR' | 'ADMINISTRADOR'
type Status = 'ativo' | 'inativo'

interface UsuarioGerencia {
  id: number
  login: string
  nome: string | null
  tipo: Tipo
  status: Status
  ultimo_acesso: string | null
}

interface FormState {
  id: number | null
  login: string
  tipo: Tipo
  status: Status
}

const FORM_VAZIO: FormState = { id: null, login: '', tipo: 'COORDENADOR', status: 'ativo' }

function GerenciaConfiguracao() {
  const navigate = useNavigate()

  const [autorizado, setAutorizado] = useState(false)
  const [usuarios, setUsuarios] = useState<UsuarioGerencia[]>([])
  const [carregando, setCarregando] = useState(true)
  const [erro, setErro] = useState('')

  const [modalAberto, setModalAberto] = useState(false)
  const [form, setForm] = useState<FormState>(FORM_VAZIO)
  const [salvando, setSalvando] = useState(false)
  const [erroForm, setErroForm] = useState('')

  const carregarUsuarios = async () => {
    setCarregando(true)
    setErro('')
    try {
      const resp = await gerenciaFetch('/gerencia/api/usuarios')
      if (resp.status === 403) {
        navigate('/gerencia/consulta')
        return
      }
      const data = await resp.json()
      if (data.sucesso) {
        setUsuarios(data.usuarios)
        setAutorizado(true)
      } else {
        setErro(data.erro || 'Erro ao carregar usuários.')
      }
    } catch {
      setErro('Erro de conexão com o servidor.')
    } finally {
      setCarregando(false)
    }
  }

  useEffect(() => {
    if (!getToken()) { navigate('/gerencia'); return }
    // carregarUsuarios só chama setState após o `await` do fetch — assíncrono, não síncrono
    // eslint-disable-next-line react-hooks/set-state-in-effect
    carregarUsuarios()
  }, [])

  const abrirModalNovo = () => {
    setForm(FORM_VAZIO)
    setErroForm('')
    setModalAberto(true)
  }

  const abrirModalEditar = (u: UsuarioGerencia) => {
    setForm({ id: u.id, login: u.login, tipo: u.tipo, status: u.status })
    setErroForm('')
    setModalAberto(true)
  }

  const fecharModal = () => {
    if (salvando) return
    setModalAberto(false)
  }

  const handleSalvar = async () => {
    if (!form.login.trim()) {
      setErroForm('Informe o login.')
      return
    }
    setSalvando(true)
    setErroForm('')
    try {
      const resp = await gerenciaFetch(
        form.id ? `/gerencia/api/usuarios/${form.id}` : '/gerencia/api/usuarios',
        {
          method: form.id ? 'PUT' : 'POST',
          body: JSON.stringify({ login: form.login.trim(), tipo: form.tipo, status: form.status }),
        }
      )
      const data = await resp.json()
      if (data.sucesso) {
        setModalAberto(false)
        carregarUsuarios()
      } else {
        setErroForm(data.mensagem || 'Erro ao salvar usuário.')
      }
    } catch {
      setErroForm('Erro de conexão com o servidor.')
    } finally {
      setSalvando(false)
    }
  }

  if (!autorizado && carregando) {
    return (
      <div className="gd-body">
        <GerenciaHeader titulo="Configuração" />
        <main className="gd-main">
          <div className="gd-card gd-buscando-card">
            <div className="gd-spinner" />
            <span>Carregando...</span>
          </div>
        </main>
      </div>
    )
  }

  return (
    <div className="gd-body">
      <GerenciaHeader titulo="Configuração" />

      <main className="gd-main">
        <div className="gc-tabs">
          <button className="gc-tab gc-tab-active">Usuários</button>
        </div>

        <div className="gd-card">
          <div className="gc-card-header">
            <h2 className="gd-card-title" style={{ marginBottom: 0 }}>Usuários do Sistema</h2>
            <div className="gc-card-header-actions">
              <button className="gc-btn-voltar" onClick={() => navigate('/gerencia/consulta')}>Voltar</button>
              <button className="gc-btn-novo" onClick={abrirModalNovo}>+ Novo Usuário</button>
            </div>
          </div>

          {erro && <div className="gd-error">{erro}</div>}

          {!erro && (
            <div className="gd-table-wrap" style={{ marginTop: 20 }}>
              <table className="gd-table">
                <thead>
                  <tr>
                    <th>Login</th>
                    <th>Nome</th>
                    <th>Tipo</th>
                    <th>Último Acesso</th>
                    <th>Status</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {usuarios.map(u => (
                    <tr key={u.id}>
                      <td className="gd-td-mono">{u.login}</td>
                      <td className="gd-td-nome">{u.nome || '—'}</td>
                      <td>
                        <span className={`gc-badge-tipo ${u.tipo === 'ADMINISTRADOR' ? 'gc-tipo-admin' : ''}`}>
                          {u.tipo === 'ADMINISTRADOR' ? 'Administrador' : 'Coordenador'}
                        </span>
                      </td>
                      <td className="gd-td-data">{u.ultimo_acesso || 'Nunca acessou'}</td>
                      <td>
                        <span className={`gc-badge-status ${u.status === 'ativo' ? 'gc-status-ativo' : 'gc-status-inativo'}`}>
                          {u.status === 'ativo' ? 'Ativo' : 'Inativo'}
                        </span>
                      </td>
                      <td className="gd-td-acao">
                        <button className="gc-btn-editar" onClick={() => abrirModalEditar(u)}>Editar</button>
                      </td>
                    </tr>
                  ))}
                  {usuarios.length === 0 && (
                    <tr>
                      <td colSpan={6} style={{ textAlign: 'center', color: '#5a6a88', padding: '24px 0' }}>
                        Nenhum usuário cadastrado.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </main>

      {modalAberto && (
        <div className="gd-modal-overlay" onClick={e => { if (e.target === e.currentTarget) fecharModal() }}>
          <div className="gd-modal">
            <div className="gd-modal-header">
              <div>
                <div className="gd-modal-nome">{form.id ? 'Editar Usuário' : 'Novo Usuário'}</div>
                <div className="gd-modal-subtipo">Acesso ao painel /gerencia</div>
              </div>
              {!salvando && <button className="gd-modal-close" onClick={fecharModal}>✕</button>}
            </div>

            <div className="gc-modal-form">
              <label className="gc-form-label">
                Login (usuário Vitae)
                <input
                  className="gc-form-input"
                  type="text"
                  value={form.login}
                  onChange={e => setForm(f => ({ ...f, login: e.target.value.toUpperCase() }))}
                  autoFocus
                  disabled={salvando}
                />
              </label>

              <label className="gc-form-label">
                Tipo
                <select
                  className="gc-form-input"
                  value={form.tipo}
                  onChange={e => setForm(f => ({ ...f, tipo: e.target.value as Tipo }))}
                  disabled={salvando}
                >
                  <option value="COORDENADOR">Coordenador</option>
                  <option value="ADMINISTRADOR">Administrador</option>
                </select>
              </label>

              <label className="gc-form-checkbox">
                <input
                  type="checkbox"
                  checked={form.status === 'ativo'}
                  onChange={e => setForm(f => ({ ...f, status: e.target.checked ? 'ativo' : 'inativo' }))}
                  disabled={salvando}
                />
                Ativo
              </label>

              {erroForm && <div className="gd-error">{erroForm}</div>}

              <div className="gd-modal-actions">
                <button className="gd-btn-gerar" onClick={handleSalvar} disabled={salvando}>
                  {salvando ? 'Salvando...' : 'Salvar'}
                </button>
                <button className="gd-btn-cancelar" onClick={fecharModal} disabled={salvando}>Cancelar</button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default GerenciaConfiguracao
