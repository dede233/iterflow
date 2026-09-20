import { api } from './client'
export const startEditing=(entity_type:string,entity_id:number)=>api.post('/editing/start',{entity_type,entity_id}).then(r=>r.data)
export const editingHeartbeat=(entity_type:string,entity_id:number)=>api.post('/editing/heartbeat',{entity_type,entity_id}).then(r=>r.data)
export const endEditing=(entity_type:string,entity_id:number)=>api.post('/editing/end',{entity_type,entity_id}).then(r=>r.data)
