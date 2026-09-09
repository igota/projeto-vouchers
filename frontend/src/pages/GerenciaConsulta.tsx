import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { clearToken, gerenciaFetch, getToken } from '../gerenciaApi'
import './GerenciaConsulta.css'

type TipoBusca = 'nome' | 'identificador'
type ModalStatus =
  | 'verificando'
  | 'sem_voucher'
  | 'nao_utilizado'
  | 'ativo'
  | 'gerando'
  | 'substituindo'
  | 'sucesso'
  | 'confirmar_desativar'
  | 'desativando'
  | 'desativado'
  | 'erro'

interface Usuario {
  id_credencial: string
  nome: string
  tipo_usuario: string
  tipo_credencial: string
  numero_cartao: string
  identificador: string
  codigo_instalacao: string
  email: string | null
  status: string | null
}

function GerenciaConsulta() {
  const navigate = useNavigate()

  const [tipoBusca, setTipoBusca] = useState<TipoBusca>('nome')
  const [valor, setValor] = useState('')
  const [buscando, setBuscando] = useState(false)
  const [resultados, setResultados] = useState<Usuario[] | null>(null)
  const [erro, setErro] = useState('')

  const [voucherStatus,      setVoucherStatus]      = useState<Record<string, string>>({})
  const [voucherPeriodo,     setVoucherPeriodo]     = useState<Record<string, string>>({})
  const [voucherInicio,      setVoucherInicio]      = useState<Record<string, string>>({})
  const [voucherExpira,      setVoucherExpira]      = useState<Record<string, string>>({})
  const [voucherDispositivo, setVoucherDispositivo] = useState<Record<string, string>>({})

  const [usuarioSelecionado, setUsuarioSelecionado] = useState<Usuario | null>(null)
  const [modalStatus, setModalStatus] = useState<ModalStatus | null>(null)
  const [voucherModal, setVoucherModal]       = useState('')
  const [dataVoucher, setDataVoucher]         = useState('')
  const [dataInicioModal, setDataInicioModal] = useState('')
  const [dataExpModal, setDataExpModal]       = useState('')
  const [erroModal, setErroModal]             = useState('')

  // =====================================================
  // ESTADOS DO PERÍODO
  // =====================================================
  const [duracaoValor, setDuracaoValor] = useState<string>('')
  const [duracaoUnidade, setDuracaoUnidade] = useState<string>('Dias')

  useEffect(() => {
    if (!getToken()) { navigate('/gerencia'); return }
    gerenciaFetch('/gerencia/api/me').then(r => {
      if (!r.ok) { clearToken(); navigate('/gerencia') }
    })
  }, [])

  const handleLogout = async () => {
    await gerenciaFetch('/gerencia/logout', { method: 'POST' })
    clearToken()
    navigate('/gerencia')
  }

  const verificarStatusEmParalelo = (usuarios: Usuario[]) => {
    usuarios.forEach(u => {
      gerenciaFetch('/gerencia/api/verificar-voucher', {
        method: 'POST',
        body: JSON.stringify({ id_credencial: u.id_credencial, numero_cartao: u.numero_cartao }),
      })
        .then(r => r.json())
        .then(data => {
          if (data.sucesso) {
            setVoucherStatus(prev => ({ ...prev, [u.id_credencial]: data.situacao }))
            if (data.periodo)        setVoucherPeriodo(prev     => ({ ...prev, [u.id_credencial]: data.periodo }))
            if (data.data_inicio)    setVoucherInicio(prev      => ({ ...prev, [u.id_credencial]: data.data_inicio }))
            if (data.data_expiracao) setVoucherExpira(prev      => ({ ...prev, [u.id_credencial]: data.data_expiracao }))
            if (data.dispositivo)    setVoucherDispositivo(prev => ({ ...prev, [u.id_credencial]: data.dispositivo }))
          }
        })
        .catch(() => {})
    })
  }

  const handleBuscar = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!valor.trim()) return
    setBuscando(true)
    setErro('')
    setResultados(null)
    setVoucherStatus({})
    setVoucherPeriodo({})
    setVoucherInicio({})
    setVoucherExpira({})
    setVoucherDispositivo({})
    try {
      const resp = await gerenciaFetch('/gerencia/api/buscar-usuario', {
        method: 'POST',
        body: JSON.stringify({ tipo: tipoBusca, valor: valor.trim() }),
      })
      const data = await resp.json()
      if (data.sucesso) {
        setResultados(data.resultados)
        if (data.resultados.length === 0) {
          setErro('Nenhum usuário encontrado.')
        } else {
          verificarStatusEmParalelo(data.resultados)
        }
      } else {
        setErro(data.erro || 'Erro na busca.')
      }
    } catch {
      setErro('Erro de conexão com o servidor.')
    } finally {
      setBuscando(false)
    }
  }

  const handleTipoChange = (tipo: TipoBusca) => {
    setTipoBusca(tipo)
    setValor('')
    setResultados(null)
    setErro('')
  }

  const abrirModal = async (usuario: Usuario) => {
    setUsuarioSelecionado(usuario)
    setModalStatus('verificando')
    setVoucherModal('')
    setDataVoucher('')
    setDataInicioModal('')
    setDataExpModal('')
    setErroModal('')
    setDuracaoValor('')
    setDuracaoUnidade('Dias')

    try {
      const resp = await gerenciaFetch('/gerencia/api/verificar-voucher', {
        method: 'POST',
        body: JSON.stringify({
          id_credencial: usuario.id_credencial,
          numero_cartao: usuario.numero_cartao,
        }),
      })
      const data = await resp.json()
      if (!data.sucesso) {
        setErroModal(data.erro || 'Erro ao verificar voucher.')
        setModalStatus('erro')
        return
      }
      setVoucherModal(data.voucher_code || '')
      setDataVoucher(data.data_impressao || '')
      setDataInicioModal(data.data_inicio || '')
      setDataExpModal(data.data_expiracao || '')
      setModalStatus(data.situacao as ModalStatus)
    } catch {
      setErroModal('Erro de conexão com o servidor.')
      setModalStatus('erro')
    }
  }
  // =====================================================
  // GERAR VOUCHER (COM PERÍODO ESCOLHIDO)
  // =====================================================
  const handleGerarVoucher = async () => {
  if (!usuarioSelecionado) return
  
  const valorNumerico = Number(duracaoValor)
  if (!duracaoValor || valorNumerico <= 0) {
    setErroModal('Informe um valor válido para o período.')
    setModalStatus('erro')
    return
  }
  
  setModalStatus('gerando')
  try {
    const resp = await gerenciaFetch('/gerencia/api/gerar-voucher', {
      method: 'POST',
      body: JSON.stringify({
        id_credencial: usuarioSelecionado.id_credencial,
        numero_cartao: usuarioSelecionado.numero_cartao,
        nome: usuarioSelecionado.nome,
        tipo_usuario: usuarioSelecionado.tipo_usuario,
        duracao_valor: valorNumerico,
        duracao_unidade: duracaoUnidade,
      }),
    })
      const data = await resp.json()
      if (data.sucesso) {
        setVoucherModal(data.voucher_code)
        setModalStatus('sucesso')
      } else {
        setErroModal(data.mensagem || data.erro || 'Erro ao gerar voucher.')
        setModalStatus('erro')
      }
    } catch {
      setErroModal('Erro de conexão com o servidor.')
      setModalStatus('erro')
    }
  }

  // =====================================================
  // SUBSTITUIR VOUCHER (COM PERÍODO ESCOLHIDO)
  // =====================================================
  const handleSubstituirVoucher = async () => {
    if (!usuarioSelecionado) return

    const valorNumerico = Number(duracaoValor)
    if (!duracaoValor || valorNumerico <= 0) {
      setErroModal('Informe um valor válido para o período.')
      setModalStatus('erro')
      return
    }

    setModalStatus('substituindo')
    try {
      const resp = await gerenciaFetch('/gerencia/api/substituir-voucher', {
        method: 'POST',
        body: JSON.stringify({
          voucher_antigo: voucherModal,
          id_credencial: usuarioSelecionado.id_credencial,
          numero_cartao: usuarioSelecionado.numero_cartao,
          nome: usuarioSelecionado.nome,
          tipo_usuario: usuarioSelecionado.tipo_usuario,
          duracao_valor: valorNumerico,
          duracao_unidade: duracaoUnidade,
        }),
      })
      const data = await resp.json()
      if (data.sucesso) {
        setVoucherModal(data.voucher_code)
        setModalStatus('sucesso')
      } else {
        setErroModal(data.mensagem || data.erro || 'Erro ao substituir voucher.')
        setModalStatus('erro')
      }
    } catch {
      setErroModal('Erro de conexão com o servidor.')
      setModalStatus('erro')
    }
  }

  const abrirModalDesativar = (usuario: Usuario, e: React.MouseEvent) => {
    e.stopPropagation()
    setUsuarioSelecionado(usuario)
    setVoucherModal('')
    setDataVoucher('')
    setErroModal('')
    setModalStatus('confirmar_desativar')
  }

  const handleDesativarVoucher = async () => {
    if (!usuarioSelecionado) return
    setModalStatus('desativando')
    try {
      const resp = await gerenciaFetch('/gerencia/api/desativar-voucher', {
        method: 'POST',
        body: JSON.stringify({
          id_credencial: usuarioSelecionado.id_credencial,
          numero_cartao: usuarioSelecionado.numero_cartao,
        }),
      })
      const data = await resp.json()
      setErroModal(data.sucesso ? '' : (data.mensagem || 'Erro ao desativar.'))
      setModalStatus('desativado')
    } catch {
      setErroModal('Erro de conexão com o servidor.')
      setModalStatus('desativado')
    }
  }

  const fecharModal = () => {
    setModalStatus(null)
    setUsuarioSelecionado(null)
    setVoucherModal('')
    setDataVoucher('')
    setErroModal('')
  }

  const isLoading = modalStatus === 'verificando' || modalStatus === 'gerando' || modalStatus === 'substituindo' || modalStatus === 'desativando'

  // =====================================================
  // RENDER
  // =====================================================
  return (
    <div className="gd-body">
      <header className="gd-header">
        <span className="gd-header-title">HRN · Gerenciamento de Vouchers</span>
        <button className="gd-logout-btn" onClick={handleLogout}>Sair</button>
      </header>

      <main className="gd-main">
        {/* Card de busca */}
        <div className="gd-card">
          <h2 className="gd-card-title">Consultar Usuário</h2>
          <form onSubmit={handleBuscar}>
            <div className="gd-radio-group">
              <label className={`gd-radio-label ${tipoBusca === 'nome' ? 'active' : ''}`}>
                <input type="radio" name="tipoBusca" value="nome"
                  checked={tipoBusca === 'nome'} onChange={() => handleTipoChange('nome')} />
                <span className="gd-radio-circle" />
                Nome Completo
              </label>
              <label className={`gd-radio-label ${tipoBusca === 'identificador' ? 'active' : ''}`}>
                <input type="radio" name="tipoBusca" value="identificador"
                  checked={tipoBusca === 'identificador'} onChange={() => handleTipoChange('identificador')} />
                <span className="gd-radio-circle" />
                Identificador do Cartão
              </label>
            </div>
            <div className="gd-search-row">
              <input
                className="gd-search-input"
                type="text"
                placeholder={tipoBusca === 'nome' ? 'Digite o nome...' : 'Digite o identificador...'}
                value={valor}
                onChange={e => setValor(e.target.value.toUpperCase())}
                autoFocus
              />
              <button className="gd-search-btn" type="submit" disabled={buscando || !valor.trim()}>
                {buscando ? 'Buscando...' : 'Buscar'}
              </button>
            </div>
          </form>
          {erro && <div className="gd-error">{erro}</div>}
        </div>

        {/* Loading da busca */}
        {buscando && (
          <div className="gd-card gd-buscando-card">
            <div className="gd-spinner" />
            <span>Buscando usuário...</span>
          </div>
        )}

        {/* Resultados */}
        {resultados && resultados.length > 0 && (
          <div className="gd-card gd-results-card">
            <h3 className="gd-results-title">
              {resultados.length} resultado{resultados.length !== 1 ? 's' : ''} — clique em uma linha para ver o voucher
            </h3>
            <div className="gd-table-wrap">
              <table className="gd-table">
                <thead>
                  <tr>
                    <th>Nome</th>
                    <th>Tipo de Usuário</th>
                    <th>Identificador do Cartão</th>
                    <th>Dispositivo</th>
                    <th>Período</th>
                    <th>Início</th>
                    <th>Expira</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {resultados.map((u, i) => (
                    <tr
                      key={i}
                      className={[
                        'gd-tr-clickable',
                        voucherStatus[u.id_credencial] === 'ativo'        ? 'gd-row-ativo'        : '',
                        voucherStatus[u.id_credencial] === 'nao_utilizado' ? 'gd-row-nao-utilizado' : '',
                      ].join(' ')}
                      onClick={() => abrirModal(u)}
                    >
                      <td className="gd-td-nome">{u.nome || '—'}</td>
                      <td><span className="gd-badge-tipo">{u.tipo_usuario || '—'}</span></td>
                      <td className="gd-td-mono">{u.identificador || '—'}</td>
                      <td>{voucherStatus[u.id_credencial] === undefined ? <span className="gd-dot-loading" /> : (voucherDispositivo[u.id_credencial] || '—')}</td>
                      <td className="gd-td-periodo">{voucherStatus[u.id_credencial] === undefined ? <span className="gd-dot-loading" /> : (voucherPeriodo[u.id_credencial] || '—')}</td>
                      <td className="gd-td-data">{voucherStatus[u.id_credencial] === undefined ? <span className="gd-dot-loading" /> : (voucherInicio[u.id_credencial] || '—')}</td>
                      <td className="gd-td-data">{voucherStatus[u.id_credencial] === undefined ? <span className="gd-dot-loading" /> : (voucherExpira[u.id_credencial] || '—')}</td>
                      <td className="gd-td-acao">
                        {voucherStatus[u.id_credencial] === 'sem_voucher' && (
                          <button
                            className="gd-btn-gerar-linha"
                            onClick={e => { e.stopPropagation(); abrirModal(u) }}
                            title="Gerar voucher"
                          >
                            Gerar
                          </button>
                        )}
                        {(voucherStatus[u.id_credencial] === 'ativo' || voucherStatus[u.id_credencial] === 'nao_utilizado') && (
                          <button
                            className="gd-btn-desativar"
                            onClick={e => abrirModalDesativar(u, e)}
                            title="Desativar voucher"
                          >
                            Desativar
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </main>

      {/* Modal */}
      {modalStatus && usuarioSelecionado && (
        <div className="gd-modal-overlay" onClick={e => { if (e.target === e.currentTarget && !isLoading) fecharModal() }}>
          <div className="gd-modal">
            <div className="gd-modal-header">
              <div>
                <div className="gd-modal-nome">{usuarioSelecionado.nome}</div>
                <div className="gd-modal-subtipo">{usuarioSelecionado.tipo_usuario || 'Tipo desconhecido'}</div>
              </div>
              {!isLoading && (
                <button className="gd-modal-close" onClick={fecharModal}>✕</button>
              )}
            </div>

            <div className="gd-modal-body">

              {isLoading && (
                <div className="gd-modal-loading">
                  <div className="gd-spinner" />
                  <p>
                    {modalStatus === 'verificando' && 'Verificando voucher...'}
                    {modalStatus === 'gerando' && 'Gerando voucher...'}
                    {modalStatus === 'substituindo' && 'Cancelando voucher atual e gerando novo...'}
                  </p>
                </div>
              )}

              {/* =============================================
                  SITUAÇÕES
                  ============================================= */}

              {/* Sem voucher — mostrar opção de período */}
              {modalStatus === 'sem_voucher' && (
                <>
                  <div className="gd-modal-icon gd-icon-warn">⚠</div>
                  <p className="gd-modal-msg">Usuário não possui voucher ativo.</p>
                  
                  {/* Campo de período */}
                  <div className="gd-periodo-group">
                    <label className="gd-periodo-label">Período do Voucher</label>
                    <div className="gd-duracao-row">
                      <input
                        type="number"
                        min="0"
                        step="1"
                        placeholder="Digite o valor"
                        value={duracaoValor}
                        onChange={e => setDuracaoValor(e.target.value)}
                        className="gd-duracao-input"
                      />
                      <select
                        value={duracaoUnidade}
                        onChange={e => setDuracaoUnidade(e.target.value)}
                        className="gd-duracao-select"
                      >
                        <option value="Minutos">Minutos</option>
                        <option value="Horas">Horas</option>
                        <option value="Dias">Dias</option>
                      </select>
                    </div>
                  </div>

                  <div className="gd-modal-actions">
                    <button className="gd-btn-gerar" onClick={handleGerarVoucher}>Gerar Voucher</button>
                    <button className="gd-btn-cancelar" onClick={fecharModal}>Cancelar</button>
                  </div>
                </>
              )}

              {/* Voucher gerado mas não utilizado */}
              {modalStatus === 'nao_utilizado' && (
                <>
                  <div className="gd-modal-icon gd-icon-info">!</div>
                  <p className="gd-modal-msg">Voucher gerado mas ainda não foi utilizado:</p>
                  <div className="gd-modal-voucher">{voucherModal}</div>
                  {dataVoucher && <p className="gd-modal-data">Gerado em {dataVoucher}</p>}
                  <div className="gd-modal-actions">
                    <button className="gd-btn-cancelar" onClick={fecharModal}>Fechar</button>
                  </div>
                </>
              )}

              {/* Voucher ativo — mostrar opção de período para substituir */}
              {modalStatus === 'ativo' && (
                <>
                  <div className="gd-modal-icon gd-icon-ok">✓</div>
                  <p className="gd-modal-msg">Usuário possui um voucher ativo:</p>
                  <div className="gd-modal-voucher">{voucherModal}</div>
                  <div className="gd-datas-omada">
                    {dataInicioModal && <span>Início: <strong>{dataInicioModal}</strong></span>}
                    {dataExpModal    && <span>Expira: <strong>{dataExpModal}</strong></span>}
                  </div>
                  {dataVoucher && <p className="gd-modal-data">Gerado em {dataVoucher}</p>}
                  <p className="gd-modal-msg" style={{ marginTop: 4 }}>Deseja cancelar o atual e gerar um novo?</p>
                  
                  {/* Campo de período */}
                  <div className="gd-periodo-group">
                    <label className="gd-periodo-label">Novo período</label>
                    <div className="gd-duracao-row">
                      <input
                        type="number"
                        min="1"
                        value={duracaoValor}
                        onChange={e => setDuracaoValor(e.target.value)}
                        className="gd-duracao-input"
                      />
                      <select
                        value={duracaoUnidade}
                        onChange={e => setDuracaoUnidade(e.target.value)}
                        className="gd-duracao-select"
                      >
                        <option value="Minutos">Minutos</option>
                        <option value="Horas">Horas</option>
                        <option value="Dias">Dias</option>
                      </select>
                    </div>
                  </div>

                  <div className="gd-modal-actions">
                    <button className="gd-btn-gerar" onClick={handleSubstituirVoucher}>Sim, cancelar e gerar novo</button>
                    <button className="gd-btn-cancelar" onClick={fecharModal}>Não, manter atual</button>
                  </div>
                </>
              )}

              {/* Confirmação de desativação */}
              {modalStatus === 'confirmar_desativar' && (
                <>
                  <div className="gd-modal-icon gd-icon-warn">⚠</div>
                  <p className="gd-modal-msg">
                    Deseja desativar o voucher ativo de<br />
                    <strong style={{ color: '#f0f4ff' }}>{usuarioSelecionado?.nome}</strong>?
                  </p>
                  <p className="gd-modal-data" style={{ color: '#5a6a88', marginTop: 4 }}>
                    Esta ação apenas desativa o acesso — nenhum novo voucher será gerado.
                  </p>
                  <div className="gd-modal-actions">
                    <button className="gd-btn-desativar-modal" onClick={handleDesativarVoucher}>Confirmar desativação</button>
                    <button className="gd-btn-cancelar" onClick={fecharModal}>Cancelar</button>
                  </div>
                </>
              )}

              {/* Resultado da desativação */}
              {modalStatus === 'desativado' && (
                <>
                  <div className={`gd-modal-icon ${erroModal ? 'gd-icon-err' : 'gd-icon-ok'}`}>
                    {erroModal ? '✕' : '✓'}
                  </div>
                  <p className="gd-modal-msg">{erroModal || 'Voucher desativado com sucesso!'}</p>
                  <div className="gd-modal-actions">
                    <button className="gd-btn-cancelar" onClick={fecharModal}>Fechar</button>
                  </div>
                </>
              )}

              {/* Sucesso */}
              {modalStatus === 'sucesso' && (
                <>
                  <div className="gd-modal-icon gd-icon-ok">✓</div>
                  <p className="gd-modal-msg">Voucher gerado com sucesso!</p>
                  <div className="gd-modal-voucher">{voucherModal}</div>
                  <div className="gd-modal-actions">
                    <button className="gd-btn-cancelar" onClick={fecharModal}>Fechar</button>
                  </div>
                </>
              )}

              {/* Erro */}
              {modalStatus === 'erro' && (
                <>
                  <div className="gd-modal-icon gd-icon-err">✕</div>
                  <p className="gd-modal-msg">{erroModal}</p>
                  <div className="gd-modal-actions">
                    <button className="gd-btn-cancelar" onClick={fecharModal}>Fechar</button>
                  </div>
                </>
              )}

            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default GerenciaConsulta