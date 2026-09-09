import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { kioskFetch } from '../kioskApi'
import './LeitorCartao.css'

function LeitorCartao() {
  const navigate = useNavigate()
  const [isApproaching, setIsApproaching] = useState(false)
  const [isReading, setIsReading] = useState(false)
  const [feedback, setFeedback] = useState('')
  const [showSuccess, setShowSuccess] = useState(false)
  const [usuarioNome, setUsuarioNome] = useState('')

  const bufferRef = useRef('')
  const bufferTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Animação em looping
  useEffect(() => {
    const interval = setInterval(() => {
      if (!isReading && !showSuccess) {
        setIsApproaching(prev => !prev)
      }
    }, 3000)
    return () => clearInterval(interval)
  }, [isReading, showSuccess])

  // Captura input do leitor de cartão via keydown no document (sem input focado)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (isReading || showSuccess) return

      if (e.key === 'Enter') {
        processarBuffer()
        return
      }

      if (e.key.length === 1) {
        bufferRef.current += e.key

        if (bufferTimeoutRef.current) clearTimeout(bufferTimeoutRef.current)
        bufferTimeoutRef.current = setTimeout(() => {
          processarBuffer()
        }, 120)
      }
    }

    document.addEventListener('keydown', handleKeyDown)
    return () => {
      document.removeEventListener('keydown', handleKeyDown)
      if (bufferTimeoutRef.current) clearTimeout(bufferTimeoutRef.current)
    }
  }, [isReading, showSuccess])

  const processarBuffer = () => {
    const valor = bufferRef.current
    bufferRef.current = ''

    if (!valor) return

    let apenasNumeros = valor.replace(/\D/g, '')

    if (apenasNumeros.length > 1 && apenasNumeros.startsWith('0')) {
      apenasNumeros = apenasNumeros.substring(1)
    }

    console.log(`🔥 Input: "${apenasNumeros}" (${apenasNumeros.length} dígitos)`)

    const digitosValidos = [7, 8, 9, 10, 14]
    if (digitosValidos.includes(apenasNumeros.length)) {
      console.log(`✅ Cartão completo: ${apenasNumeros}`)
      iniciarLeitura(apenasNumeros)
    } else if (apenasNumeros.length > 0) {
      console.log(`⚠️ Cartão ignorado: ${apenasNumeros.length} dígitos (aceitos: 7, 8, 9, 10, 14)`)
    }
  }

  const buscarUsuario = async (id: string) => {
    try {
      const response = await kioskFetch('/api/buscar-cartao', {
        method: 'POST',
        body: JSON.stringify({ numero_cartao: id })
      })

      const data = await response.json()

      if (data.encontrado) {
        setUsuarioNome(data.usuario.nome)
        setShowSuccess(true)
        setFeedback('')
        setIsReading(false)

        setTimeout(() => {
          navigate('/voucher', {
            state: {
              numero_cartao: id,
              usuario_nome: data.usuario.nome,
              usuario_tipo: data.usuario.tipo_usuario
            }
          })
        }, 2000)
      } else {
        setFeedback(`❌ ${data.mensagem}`)
        finalizarLeitura(true)
      }
    } catch (error) {
      console.error('Erro:', error)
      setFeedback('❌ Erro de conexão com o servidor')
      finalizarLeitura(true)
    }
  }

  const iniciarLeitura = (id: string) => {
    setIsReading(true)
    setFeedback('📡 Buscando dados do usuário...')
    buscarUsuario(id)
  }

  const finalizarLeitura = (isError: boolean = false) => {
    setTimeout(() => {
      setIsReading(false)
      bufferRef.current = ''

      if (isError) {
        setTimeout(() => setFeedback(''), 3000)
      } else {
        setFeedback('')
      }
    }, 2000)
  }

  return (
    <div className="container">
      <h1 className="title"></h1>

      {/* Animação de sucesso */}
      {showSuccess && (
        <div className="success-overlay">
          <div className="success-animation">
            <div className="check-container">
              <div className="check-circle">
                <svg className="check-svg" viewBox="0 0 100 100">
                  <circle
                    className="check-circle-bg"
                    cx="50" cy="50" r="45"
                    fill="none" stroke="#4CAF50" strokeWidth="4"
                  />
                  <circle
                    className="check-circle-progress"
                    cx="50" cy="50" r="45"
                    fill="none" stroke="#4CAF50" strokeWidth="6" strokeLinecap="round"
                  />
                  <polyline
                    className="check-mark"
                    points="30,50 48,68 72,38"
                    fill="none" stroke="#4CAF50" strokeWidth="6"
                    strokeLinecap="round" strokeLinejoin="round"
                  />
                </svg>
                <div className="check-glow"></div>
              </div>
            </div>
            <h2 className="success-title">CARTÃO APROVADO!</h2>
            <p className="success-name">{usuarioNome}</p>
            <p className="success-subtext">Redirecionando...</p>
          </div>
        </div>
      )}

      <div className="reader-area">
        <div className={`card-reader ${isApproaching && !isReading && !showSuccess ? 'active' : ''} ${isReading ? 'reading' : ''}`}>
          <div className="reader-slot">
            {isReading && <div className="scan-line"></div>}
          </div>
          <div className={`reader-led ${isReading ? 'reading' : ''}`}></div>
          <div className={`reader-glow ${isApproaching && !isReading && !showSuccess ? 'active' : ''}`}></div>
        </div>

        <div className={`badge ${isApproaching && !isReading && !showSuccess ? 'approaching' : 'away'} ${isReading ? 'reading' : ''}`}>
          <div className="badge-chip"></div>
          <div className="badge-stripe"></div>
          <div className="badge-text">VOUCHER<br />ACCESS</div>
          <div className={`badge-glow ${isApproaching && !isReading && !showSuccess ? 'active' : ''}`}></div>
        </div>

        <div className={`proximity-effect ${isApproaching && !isReading && !showSuccess ? 'active' : ''}`}>
          <div className="proximity-ring"></div>
          <div className="proximity-ring"></div>
          <div className="proximity-ring"></div>
          <div className="proximity-ring"></div>
        </div>

        <div className={`connection-line ${isApproaching && !isReading && !showSuccess ? 'active' : ''}`}></div>
      </div>

      <div className="message-box">
        <p className={`instruction ${isReading ? 'pulse' : ''}`}>
          {feedback || 'Aproxime seu Cartão do Leitor'}
        </p>
        <p className="subtext">
          Aproxime o crachá do leitor para resgatar seu voucher
        </p>

        {isReading && (
          <div className="progress-container">
            <div className="progress-bar">
              <div className="progress-fill"></div>
            </div>
            <p className="progress-text">Verificando...</p>
          </div>
        )}
      </div>
    </div>
  )
}

export default LeitorCartao
