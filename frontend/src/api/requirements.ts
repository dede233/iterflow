import { api } from './client'
import type { Requirement, PageResult } from '@/types/domain'
export const listRequirements=(params={})=>api.get<PageResult<Requirement>>('/requirements',{params}).then(r=>r.data)
export const getRequirement=(id:number)=>api.get<Requirement>(`/requirements/${id}`).then(r=>r.data)
export const createRequirement=(payload:any)=>api.post('/requirements',payload).then(r=>r.data)
export const updateRequirement=(id:number,payload:any)=>api.patch(`/requirements/${id}`,payload).then(r=>r.data)
export const changeRequirementStatus=(id:number,status:string,revision:number)=>api.patch(`/requirements/${id}/status`,{status,revision}).then(r=>r.data)
export const moveRequirementVersion=(id:number,target_version_id:number,reason:string,revision:number)=>api.post(`/requirements/${id}/move-version`,{target_version_id,reason,revision}).then(r=>r.data)
