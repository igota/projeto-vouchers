import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { clearToken, gerenciaFetch, getToken } from '../gerenciaApi'
import './GerenciaHeader.css'

interface GerenciaHeaderProps {
  titulo: string
}

function GerenciaHeader({ titulo }: GerenciaHeaderProps) {
  const navigate = useNavigate()
  const [nome, setNome] = useState('')
  const [tipo, setTipo] = useState('')
  const [menuAberto, setMenuAberto] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!getToken()) { navigate('/gerencia'); return }
    gerenciaFetch('/gerencia/api/me').then(async r => {
      if (!r.ok) { clearToken(); navigate('/gerencia'); return }
      const data = await r.json()
      setNome(data.nome || data.username || '')
      setTipo(data.tipo || '')
    })
  }, [])

  useEffect(() => {
    const handleClickFora = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuAberto(false)
      }
    }
    document.addEventListener('mousedown', handleClickFora)
    return () => document.removeEventListener('mousedown', handleClickFora)
  }, [])

  const handleLogout = async () => {
    await gerenciaFetch('/gerencia/logout', { method: 'POST' })
    clearToken()
    navigate('/gerencia')
  }

  return (
    <header className="gh-header">
      <span className="gh-header-title">{titulo}</span>

      <div className="gh-user" ref={menuRef}>
        <button
          className="gh-user-icon"
          title={nome}
          onClick={() => setMenuAberto(v => !v)}
          aria-label="Menu do usuário"
        >
          <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor">
            <circle cx="12" cy="8" r="4" />
            <path d="M4 20c0-3.9 3.6-7 8-7s8 3.1 8 7v1H4v-1z" />
          </svg>
        </button>

        {menuAberto && (
          <div className="gh-dropdown">
            <div className="gh-dropdown-nome">{nome || '—'}</div>
            <div className="gh-dropdown-divider" />
            {tipo === 'ADMINISTRADOR' && (
              <button
                className="gh-dropdown-item"
                onClick={() => { setMenuAberto(false); navigate('/gerencia/configuracao') }}
              >
                Configuração
              </button>
            )}
            <button className="gh-dropdown-item gh-dropdown-sair" onClick={handleLogout}>
              Sair
            </button>
          </div>
        )}
      </div>
    </header>
  )
}

export default GerenciaHeader
