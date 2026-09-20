import { api } from './client'
export const loginApi = (username:string, password:string) => api.post('/auth/login', { username, password }).then(r => r.data)
