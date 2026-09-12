import axios from 'axios'
import { apiBase, supabase } from './supabase'

/** Axios client that always sends the signed-in user's JWT (per-account isolation). */
export const api = axios.create({
  baseURL: apiBase,
  timeout: 45000,
})

api.interceptors.request.use(async (config) => {
  if (supabase) {
    const { data } = await supabase.auth.getSession()
    const token = data.session?.access_token
    if (token) {
      config.headers = config.headers || {}
      config.headers.Authorization = `Bearer ${token}`
    }
  }
  return config
})
