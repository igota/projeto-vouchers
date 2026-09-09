import React, { useState, useEffect, useRef } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { kioskFetch } from '../kioskApi'
import './VoucherUsuario.css'

// =====================================================
// COMPONENTE TIMER EM CÍRCULO
// =====================================================
interface TimerCircleProps {
  tempoRestante: number
  totalTempo?: number
}

const TimerCircle: React.FC<TimerCircleProps> = ({
  tempoRestante,
  totalTempo = 30
}) => {
  const radius = 87
  const center = 120

  const circumference = 2 * Math.PI * radius
  const progress = (tempoRestante / totalTempo) * circumference
  const offset = circumference - progress

  // COR DO TEXTO - SEGUE A MESMA LÓGICA DA BARRA
  const getTextColor = () => {
    const percent = (tempoRestante / totalTempo) * 100
    if (percent > 66) return '#10b981' // Verde
    if (percent > 33) return '#f59e0b' // Amarelo
    return '#ef4444' // Vermelho
  }

  // COR DA BARRA
  const getBarColor = () => {
    const percent = (tempoRestante / totalTempo) * 100
    if (percent > 66) return '#10b981' // Verde
    if (percent > 33) return '#f59e0b' // Amarelo
    return '#ef4444' // Vermelho
  }

  return (
    <div className="timer-circle">
      <svg viewBox="0 0 240 240">
        <circle
          className="bg"
          cx={center}
          cy={center}
          r={radius}
        />

        <circle
          className="progress"
          cx={center}
          cy={center}
          r={radius}
          stroke={getBarColor()}
          strokeDasharray={circumference}
          strokeDashoffset={offset}
        />

        <text
          className="timer-text"
          x={center}
          y={center + 2}
          textAnchor="middle"
          dominantBaseline="middle"
          fill={getTextColor()} // COR DINÂMICA BASEADA NO TEMPO
          fontSize="70"
          fontWeight="900"
        >
          {tempoRestante}
        </text>
      </svg>
    </div>
  )
}


// =====================================================
// COMPONENTE PRINCIPAL
// =====================================================
function VoucherUsuario() {
  const location = useLocation()
  const navigate = useNavigate()

  const { numero_cartao, usuario_nome } = location.state || {}
  const [usuarioTipo, setUsuarioTipo] = useState('')
  const [status, setStatus] = useState<'loading' | 'success' | 'error' | 'confirm' | 'voucher_nao_utilizado'>('loading')

  const [mensagem, setMensagem] = useState('')
  const [voucherCode, setVoucherCode] = useState('')
  const [voucherAtivo, setVoucherAtivo] = useState('')
  const [periodo, setPeriodo] = useState('')
  const [tempoRestante, setTempoRestante] = useState(30)
  const [encerrando, setEncerrando] = useState(false)

  const chamadaRealizada = useRef(false)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // =====================================================
  // TIMER UNIFICADO (SUCCESS, VOUCHER_NAO_UTILIZADO, CONFIRM)
  // =====================================================
  useEffect(() => {
    if ((status === 'success' || status === 'voucher_nao_utilizado' || status === 'confirm') && !encerrando) {
      if (timerRef.current) clearInterval(timerRef.current)

      timerRef.current = setInterval(() => {
        setTempoRestante(prev => {
          if (prev <= 1) {
            if (timerRef.current) clearInterval(timerRef.current)
            voltarLeitor()
            return 0
          }
          return prev - 1
        })
      }, 1000)
    }

    return () => {
      if (timerRef.current) clearInterval(timerRef.current)
    }
  }, [status, encerrando])

  // =====================================================
  // CHAMADA DA API (APENAS UMA VEZ)
  // =====================================================
  useEffect(() => {
    if (chamadaRealizada.current) return
    chamadaRealizada.current = true

    if (!numero_cartao) {
      setStatus('error')
      setMensagem('Dados do cartão não encontrados')
      return
    }

    liberarVoucher()
  }, [numero_cartao])

  const liberarVoucher = async () => {
    try {
      console.log('📡 Chamando /api/liberar-voucher para:', numero_cartao)

      const response = await kioskFetch('/api/liberar-voucher', {
        method: 'POST',
        body: JSON.stringify({ numero_cartao })
      })

      const data = await response.json()
      console.log('📡 Resposta:', response.status, data)

      if (response.status === 410) {
        setStatus('voucher_nao_utilizado')
        setVoucherCode(data.voucher_code || voucherCode)
        setMensagem(data.mensagem || 'Você possui um voucher que ainda não foi utilizado')
        setTempoRestante(30)
        return
      }

      if (response.status === 409 && data.requer_confirmacao) {
        setStatus('confirm')
        setVoucherAtivo(data.voucher_ativo)
        setMensagem(data.mensagem)
        setTempoRestante(30)
        return
      }

      if (data.sucesso) {
        setStatus('success')
        setVoucherCode(data.voucher_code)
        setPeriodo(data.periodo)
        setMensagem(data.mensagem)
        setUsuarioTipo(data.tipo_usuario)
        setTempoRestante(30)
        return
      }

      setStatus('error')
      setMensagem(data.mensagem || 'Erro ao liberar voucher')

    } catch (error) {
      console.error('Erro:', error)
      setStatus('error')
      setMensagem('Erro de conexão com o servidor')
    }
  }

  const substituirVoucher = async () => {
    setStatus('loading')
    setMensagem('Cancelando voucher antigo e gerando novo...')

    try {
      const response = await kioskFetch('/api/substituir-voucher', {
        method: 'POST',
        body: JSON.stringify({
          numero_cartao: numero_cartao,
          voucher_antigo: voucherAtivo
        })
      })

      const data = await response.json()

      if (data.sucesso) {
        setStatus('success')
        setVoucherCode(data.voucher_code)
        setPeriodo(data.periodo)
        setMensagem(data.mensagem)
        setUsuarioTipo(data.tipo_usuario)
        setTempoRestante(30)
      } else {
        setStatus('error')
        setMensagem(data.mensagem || 'Erro ao substituir voucher')
      }
    } catch (error) {
      console.error('Erro:', error)
      setStatus('error')
      setMensagem('Erro de conexão com o servidor')
    }
  }

  const voltarLeitor = () => {
    setEncerrando(true)
    if (timerRef.current) clearInterval(timerRef.current)
    navigate('/')
  }

  const encerrarSessao = () => {
    if (timerRef.current) clearInterval(timerRef.current)
    voltarLeitor()
  }

  const imprimirEtiqueta = async () => {
    try {
      console.log('🏷️ Enviando etiqueta para Godex...')

      const response = await kioskFetch('/api/imprimir-etiqueta', {
        method: 'POST',
        body: JSON.stringify({ voucher_code: voucherCode })
      })

      const data = await response.json()

      if (data.sucesso) {
        console.log('✅ Etiqueta enviada com sucesso')
        setMensagem('✅ Etiqueta impressa!')
        setTimeout(() => setMensagem(''), 3000)
      } else {
        console.error('❌ Falha:', data.mensagem)
        setMensagem('❌ Falha na impressão da etiqueta')
      }
    } catch (error) {
      console.error('Erro:', error)
      setMensagem('❌ Erro de comunicação com a impressora')
    }
  }

  // =====================================================
  // TELA DE LOADING
  // =====================================================
  if (status === 'loading') {
    return (
      <div className="container voucher-container">
        <div className="loading-spinner"></div>
        <p className="loading-text">{mensagem || 'Verificando voucher...'}</p>
      </div>
    )
  }

  // =====================================================
  // TELA DE VOUCHER NÃO UTILIZADO
  // =====================================================
  if (status === 'voucher_nao_utilizado') {
    return (
      <div className="container voucher-container">
        <TimerCircle tempoRestante={tempoRestante} />
        
        

        <div className="voucher-content">
          <div className="icon-warning">⚠️</div>
          <h2>Voucher Disponível</h2>
          <p>Você possui um voucher que ainda não foi utilizado:</p>
          <div className="voucher-code-large">
            <span className="code">{voucherCode}</span>
          </div>

          <div className="button-group-row">
            <div className="btn-wrapper">
              <button className="imprimir-voucher-btn" onClick={imprimirEtiqueta}>
                🖨️ Imprimir
              </button>
            </div>
            <div className="btn-wrapper">
              <button className="encerrar-sessao-btn" onClick={encerrarSessao}>
                Encerrar
              </button>
            </div>
          </div>
        </div>
      </div>
    )
  }

  // =====================================================
  // TELA DE CONFIRMAÇÃO
  // =====================================================
  if (status === 'confirm') {
    return (
      <div className="container voucher-container">
        <TimerCircle tempoRestante={tempoRestante} />

        <div className="voucher-content">
          <div className="icon-warning">⚠️</div>
          <h2>Voucher Ativo</h2>
          <p>Você já possui um voucher ativo:</p>
          <div className="voucher-code-large">
            <span className="code">{voucherAtivo}</span>
          </div>
          <p>Deseja cancelá-lo e gerar um novo?</p>
          <div className="confirm-buttons">
            <button className="btn-confirm" onClick={substituirVoucher}>
              Sim, substituir
            </button>
            <button className="btn-cancel" onClick={voltarLeitor}>
              Não, manter atual
            </button>
          </div>
        </div>
      </div>
    )
  }

  // =====================================================
  // TELA DE ERRO
  // =====================================================
  if (status === 'error') {
    return (
      <div className="container voucher-container">
        <div className="voucher-content">
          <div className="icon-error">❌</div>
          <h2>Erro</h2>
          <p>{mensagem}</p>
          
        </div>
      </div>
    )
  }

  // =====================================================
  // TELA DE SUCESSO
  // =====================================================
  const periodoTexto = {
    '8horas': '8 horas',
    '1dia': '24 horas',
    '365dias': '365 dias'
  }[periodo] || periodo

  return (
    <div className="container voucher-container success-bg">
      <TimerCircle tempoRestante={tempoRestante} />

     

      <div className="voucher-content">
        <div className="user-card">
          <div className="user-avatar">👤</div>
          <div className="user-info">
            <h2>{usuario_nome}</h2>
            <p><strong>{usuarioTipo || 'VISITANTE'}</strong></p>
          </div>
        </div>

        <div className="voucher-card">
          <h2>🎫 Seu Voucher de {periodoTexto}</h2>
          <div className="voucher-code-large">
            <span className="code">{voucherCode}</span>
          </div>
          <p className="voucher-instruction">
            Use este código para acessar a rede <strong>HRN Wi-Fi</strong>
          </p>

          <div className="button-group-row-sucess">
            <div className="btn-wrapper-sucess">
              <button className="imprimir-voucher-btn-sucess" onClick={imprimirEtiqueta}>
                🖨️ Imprimir
              </button>
            </div>
            <div className="btn-wrapper-sucess">
              <button className="encerrar-sessao-btn-sucess" onClick={encerrarSessao}>
                Encerrar
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default VoucherUsuario