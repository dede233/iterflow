import { api } from './client'
import type { components } from '@/types/openapi.generated'

type S = components['schemas']
export type ReleaseTarget = S['ReleaseTargetOut']
export type ReleaseBatch = S['ReleaseBatchOut']
export type BatchTarget = S['ReleaseBatchTargetOut']
export type ReleaseBatches = S['ReleaseBatchesOut']
export type TargetRecord = S['TargetReleaseRecordOut']
export const batchKindLabel = { INITIAL: '首次发布', SUPPLEMENT: '补发', REPUBLISH: '重新发布' }
export const batchStatusLabel = { PLANNED: '未开始', IN_PROGRESS: '进行中', COMPLETED: '已完成', CANCELED: '已取消' }
export const platformLabel = { PC_WEB: 'PC Web', WECHAT_MINI_PROGRAM: '微信小程序', ALIPAY_MINI_PROGRAM: '支付宝小程序' }
const options = { skipConflictAlert: true }
export const listTargets = (systemId: number) => api.get<ReleaseTarget[]>(`/systems/${systemId}/release-targets`).then(r => r.data)
export const createTarget = (systemId: number, payload: S['ReleaseTargetCreate']) => api.post<ReleaseTarget>(`/systems/${systemId}/release-targets`, payload, options).then(r => r.data)
export const updateTarget = (id: number, payload: S['ReleaseTargetUpdate']) => api.patch<ReleaseTarget>(`/systems/release-targets/${id}`, payload, options).then(r => r.data)
export const versionTargets = (id: number, system_id?: number | null) => api.get<ReleaseTarget[]>(`/versions/${id}/release-targets`, { params: { system_id } }).then(r => r.data)
export const listBatches = (id: number, page = 1) => api.get<ReleaseBatches>(`/versions/${id}/release-batches`, { params: { page, page_size: 20 } }).then(r => r.data)
export const targetRecords = (params: { page: number; page_size: number; target_id?: number | null; version_id?: number | null }) => api.get<S['TargetReleasePage']>('/target-release-records', { params }).then(r => r.data)
export const targetRecordOptions = () => api.get<S['TargetReleaseOption'][]>('/target-release-records/options').then(r => r.data)

export const recordCoverage = (id: number, payload: S['ReleaseCoverageCreate']) => api.post<ReleaseBatch>(`/versions/${id}/release-coverage`, payload, options).then(r => r.data)
