import { createContext, useContext, useState, useCallback, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { getToken, setUnauthorizedHandler } from '../api/client'
import { login as loginRequest, logout as logoutRequest } from '../api/auth'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [token, setTokenState] = useState(getToken())
  const [sessionExpired, setSessionExpired] = useState(false)
  const navigate = useNavigate()

  useEffect(() => {
    setUnauthorizedHandler(() => {
      setTokenState(null)
      setSessionExpired(true)
      navigate('/login')
    })
  }, [navigate])

  const login = useCallback(async (email, password) => {
    const data = await loginRequest(email, password)
    setTokenState(getToken())
    setSessionExpired(false)
    return data
  }, [])

  const logout = useCallback(() => {
    logoutRequest()
    setTokenState(null)
    navigate('/login')
  }, [navigate])

  const value = {
    isAuthenticated: Boolean(token),
    sessionExpired,
    clearSessionExpired: () => setSessionExpired(false),
    login,
    logout,
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
