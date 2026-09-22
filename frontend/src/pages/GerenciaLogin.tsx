import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { API_BASE, setToken } from '../gerenciaApi'
import logoVoucher from '../assets/logo-voucher.png'
import logoHrn from '../assets/logo-hrn.png'
import './GerenciaLogin.css'

function GerenciaLogin() {
  const navigate = useNavigate()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const showError = (msg: string) => {
    setError(msg)
    setTimeout(() => setError(''), 4000)
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!username || !password) {
      showError('Preencha usuário e senha para acessar.')
      return
    }

    setLoading(true)
    setError('')

    try {
      const resp = await fetch(`${API_BASE}/gerencia/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
      })
      const data = await resp.json()

      if (data.success) {
        setToken(data.token)
        navigate('/gerencia/consulta')
      } else {
        showError(data.error || 'Falha na autenticação.')
      }
    } catch {
      showError('Erro de conexão com o servidor. Tente novamente.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <>
      {loading && (
        <div className="gl-loading-overlay">
          <div className="gl-spinner" />
          <div className="gl-loading-text">Validando credenciais</div>
          <div className="gl-loading-subtext">Aguardando resposta do Vitae</div>
        </div>
      )}

      <div className="gl-body">
        <div className="gl-container">
          <div className="gl-card">
            <span className="gl-badge">HRN · Vouchers</span>
            <p className="gl-subtitle">Gerenciamento de Vouchers · </p>

            <form onSubmit={handleSubmit}>
              <div className="gl-input-group">
                <input
                  type="text"
                  id="username"
                  placeholder=" "
                  value={username}
                  onChange={e => setUsername(e.target.value.toUpperCase())}
                  required
                  autoComplete="off"
                  autoFocus
                />
                <label htmlFor="username">Usuário</label>
              </div>

              <div className="gl-input-group">
                <div className="gl-password-wrap">
                  <input
                    type={showPassword ? 'text' : 'password'}
                    id="password"
                    placeholder=" "
                    value={password}
                    onChange={e => setPassword(e.target.value)}
                    required
                    autoComplete="off"
                  />
                  <label htmlFor="password">Senha</label>
                  <button
                    type="button"
                    className="gl-toggle-pw"
                    onClick={() => setShowPassword(v => !v)}
                    aria-label="Exibir senha"
                  >
                    <svg viewBox="0 0 24 24">
                      <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                      <circle cx="12" cy="12" r="3" />
                    </svg>
                  </button>
                </div>
              </div>

              <button type="submit" className="gl-submit">Acessar</button>

              {error && <div className="gl-error">{error}</div>}
            </form>
          </div>

          <div className="gl-logos">
            <img src={logoVoucher} alt="Logo Vouchers" className="gl-logo-voucher" />
            <span className="gl-logo-divider" />
            <span className="gl-logo-hrn-wrap">
              <img src={logoHrn} alt="Logo Hospital Regional Norte" className="gl-logo-hrn" />
            </span>
          </div>

          <p className="gl-footer">
            &copy; SISTEMA DE VOUCHERS | HRN
            <br />
            Powered by Igor Maciel - Todos os direitos reservados.
          </p>
        </div>
      </div>
    </>
  )
}

export default GerenciaLogin
