import { api } from './client'
import type { NotificationItem } from '@/types/domain'
import type { components } from '@/types/openapi.generated'

export const listNotifications = (unread_only = false) => api.get<NotificationItem[]>('/notifications', { params: { unread_only } }).then(r => r.data)
export const markNotificationRead = (id: number) => api.post(`/notifications/${id}/read`).then(r => r.data)
export const getNotificationUnreadCount = () => api.get<components['schemas']['NotificationUnreadCount']>('/notifications/unread-count').then(r => r.data)
export const markNotificationsReadAll = () => api.post<components['schemas']['NotificationReadAllResult']>('/notifications/read-all').then(r => r.data)
