// '??' (não '||'): em produção atrás do Nginx, VITE_API_BASE='' é intencional
// (mesma origem do front, sem precisar de CORS) e não deve cair no fallback.
export const API_BASE = import.meta.env.VITE_API_BASE ?? 'http://localhost:5000'

export const TOKEN_KEY = 'gerencia_token'

export const getToken = (): string | null => localStorage.getItem(TOKEN_KEY)
export const setToken = (token: string): void => localStorage.setItem(TOKEN_KEY, token)
export const clearToken = (): void => localStorage.removeItem(TOKEN_KEY)

export async function gerenciaFetch(path: string, options: RequestInit = {}): Promise<Response> {
  const token = getToken()
  return fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { 'X-Gerencia-Token': token } : {}),
      ...(options.headers as Record<string, string> || {}),
    },
  })
}
