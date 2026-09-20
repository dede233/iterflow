import { api } from './client'
import type { NotificationItem } from '@/types/domain'
export const listNotifications=(unread_only=false)=>api.get<NotificationItem[]>('/notifications',{params:{unread_only}}).then(r=>r.data)
export const markNotificationRead=(id:number)=>api.post(`/notifications/${id}/read`).then(r=>r.data)
