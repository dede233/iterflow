import { defineStore } from 'pinia'
import { loginApi } from '@/api/auth'

export const useAuthStore = defineStore('auth', {
  state: () => ({ accessToken: localStorage.getItem('access_token') ?? '' }),
  actions: {
    async login(username:string,password:string) {
      const data=await loginApi(username,password)
      this.accessToken=data.access_token
      localStorage.setItem('access_token',data.access_token)
      localStorage.setItem('refresh_token',data.refresh_token)
    },
    logout(){ this.accessToken=''; localStorage.clear() }
  }
})
