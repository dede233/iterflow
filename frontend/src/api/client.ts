import axios from 'axios'
import { ElMessage, ElMessageBox } from 'element-plus'

export const api = axios.create({ baseURL: '/api/v1', timeout: 15000 })

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 409) {
      await ElMessageBox.alert(error.response.data?.message ?? '数据已被其他用户修改，请刷新后重试', '编辑冲突', { type: 'warning' })
    } else if (error.response?.status === 403) {
      ElMessage.error('你没有权限执行该操作')
    }
    return Promise.reject(error)
  },
)
