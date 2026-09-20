import { api } from './client'
import type { VersionItem, PageResult } from '@/types/domain'
export const listVersions=(params={})=>api.get<PageResult<VersionItem>>('/versions',{params}).then(r=>r.data)
export const getVersion=(id:number)=>api.get<VersionItem>(`/versions/${id}`).then(r=>r.data)
export const createVersion=(payload:any)=>api.post('/versions',payload).then(r=>r.data)
export const publishVersion=(id:number,payload:any)=>api.post(`/versions/${id}/publish`,payload).then(r=>r.data)
