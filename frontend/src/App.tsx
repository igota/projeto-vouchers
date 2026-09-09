import { BrowserRouter, Routes, Route } from 'react-router-dom'
import LeitorCartao from './pages/LeitorCartao'
import VoucherUsuario from './pages/VoucherUsuario'
import GerenciaLogin from './pages/GerenciaLogin'
import GerenciaConsulta from './pages/GerenciaConsulta'
import './App.css'

function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* Quiosque */}
        <Route path="/" element={<LeitorCartao />} />
        <Route path="/voucher" element={<VoucherUsuario />} />

        {/* Gerenciamento de coordenadores */}
        <Route path="/gerencia" element={<GerenciaLogin />} />
        <Route path="/gerencia/consulta" element={<GerenciaConsulta />} />
      </Routes>
    </BrowserRouter>
  )
}

export default App
