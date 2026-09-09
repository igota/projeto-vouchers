// '??' (não '||'): em produção atrás do Nginx, VITE_API_BASE='' é intencional
// (mesma origem do front, sem precisar de CORS) e não deve cair no fallback.
export const API_BASE = import.meta.env.VITE_API_BASE ?? 'http://localhost:5000'

const KIOSK_API_KEY = import.meta.env.VITE_KIOSK_API_KEY || ''

// Chamadas do totem (leitor de cartão / emissão de voucher) não usam login —
// o backend só exige o header X-Kiosk-Key para descartar acessos aleatórios
// na rede local. Como o valor vai embutido no bundle público do frontend,
// isso não é segredo forte: só eleva a barreira acima de "nenhuma".
export async function kioskFetch(path: string, options: RequestInit = {}): Promise<Response> {
  return fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      'X-Kiosk-Key': KIOSK_API_KEY,
      ...(options.headers as Record<string, string> || {}),
    },
  })
}
