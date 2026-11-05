import { defineStore } from 'pinia'
import { api } from '@/api/client'
import { useAuthStore } from './auth'
import type { components } from '@/types/openapi.generated'
export type Announcement = components['schemas']['AnnouncementOut']
export const useAnnouncementsStore = defineStore('announcements', {
  state: () => ({ unreadCount: 0, latest: null as Announcement | null, important: null as Announcement | null, sequence: 0 }),
  actions: {
    reset() { this.sequence++; this.unreadCount = 0; this.latest = null; this.important = null },
    async refresh() {
      const auth = useAuthStore(), userId = auth.user?.id, sequence = ++this.sequence
      if (!userId) { this.reset(); return }
      try {
        const { data } = await api.get<components['schemas']['AnnouncementNotice']>('/announcements/notice')
        if (sequence !== this.sequence || userId !== auth.user?.id) return
        this.unreadCount = data.unread_count; this.latest = data.latest; this.important = data.important
      } catch { /* Announcement discovery must not block business pages. */ }
    },
    async read(item: Announcement) {
      await api.post(`/announcements/${item.id}/read`, { revision: item.revision })
      await this.refresh()
    },
  },
})
