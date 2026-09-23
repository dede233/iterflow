import { api } from './client'
import type { DashboardOverview } from '@/types/dashboard'

export const getDashboardOverview = () =>
  api.get<DashboardOverview>('/dashboard/overview').then((response) => response.data)
