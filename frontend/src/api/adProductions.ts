import { api } from '@/api/client'
import type { AdProductionKind } from '@/constants/adProduction'
import type { components, paths } from '@/types/openapi.generated'

export type AdProduction = components['schemas']['AdProductionOut']
export type AdProductionDesignerOption = components['schemas']['AdProductionDesignerOption']
type AdProductionPage = components['schemas']['AdProductionPage']
type AdProductionListParams = NonNullable<paths['/ad-productions']['get']['parameters']['query']>
type AdProductionCcOptionsParams = NonNullable<paths['/ad-productions/cc-options']['get']['parameters']['query']>
type CreateForm = components['schemas']['AdProductionCreateForm']
type UpdateForm = components['schemas']['AdProductionUpdateForm']
type AdProductionStatusChange = components['schemas']['AdProductionStatusChange']
export type AdProductionCreateFields = Pick<CreateForm, 'title' | 'content' | 'content_format' | 'receiver_id' | 'due_at' | 'kind' | 'cc_user_ids'>
export type AdProductionUpdateFields = Pick<UpdateForm,
  'work_date' | 'title' | 'content' | 'content_format' | 'status' | 'issuer' | 'receiver_id' | 'completed_by_id' | 'due_at'
> & Partial<Pick<UpdateForm, 'clear_due_at' | 'processing_result' | 'cc_user_ids'>>

export async function listAdProductions(params: AdProductionListParams): Promise<AdProductionPage> {
  return (await api.get<AdProductionPage>('/ad-productions', { params })).data
}

export async function getAdProduction(id: number, signal?: AbortSignal): Promise<AdProduction> {
  return (await api.get<AdProduction>(`/ad-productions/${id}`, { signal, skipForbiddenAlert: true })).data
}

export async function listAdProductionDesigners(kind: AdProductionKind, signal: AbortSignal): Promise<AdProductionDesignerOption[]> {
  return (await api.get<AdProductionDesignerOption[]>('/ad-productions/designer-options', {
    params: { kind }, signal, skipForbiddenAlert: true,
  })).data
}

export async function listAdProductionCcOptions(params: AdProductionCcOptionsParams, signal: AbortSignal): Promise<AdProductionDesignerOption[]> {
  return (await api.get<AdProductionDesignerOption[]>('/ad-productions/cc-options', {
    params, signal, skipForbiddenAlert: true,
  })).data
}

function adProductionForm(fields: AdProductionCreateFields | AdProductionUpdateFields, images: readonly File[], contentImages: readonly [string, File][]): FormData {
  const form = new FormData()
  for (const [key, value] of Object.entries(fields)) {
    if (value != null) form.set(key, String(value))
  }
  for (const image of images) form.append('images', image)
  for (const [key, image] of contentImages) form.append('content_images', image, key)
  return form
}

export async function createAdProduction(
  fields: AdProductionCreateFields,
  images: readonly File[],
  contentImages: readonly [string, File][],
): Promise<AdProduction> {
  return (await api.post<AdProduction>('/ad-productions', adProductionForm(fields, images, contentImages), {
    skipConflictAlert: true, skipForbiddenAlert: true,
  })).data
}

export async function updateAdProduction(
  id: number,
  fields: AdProductionUpdateFields,
  revision: number,
  images: readonly File[],
  removeImageIds: readonly number[],
  contentImages: readonly [string, File][],
): Promise<AdProduction> {
  const form = adProductionForm(fields, images, contentImages)
  form.set('revision', String(revision))
  for (const imageId of removeImageIds) form.append('remove_image_ids', String(imageId))
  return (await api.patch<AdProduction>(`/ad-productions/${id}`, form, {
    skipConflictAlert: true, skipForbiddenAlert: true,
  })).data
}

export async function updateAdProductionStatus(id: number, fields: AdProductionStatusChange): Promise<AdProduction> {
  return (await api.patch<AdProduction>(`/ad-productions/${id}/status`, fields, {
    skipConflictAlert: true, skipForbiddenAlert: true,
  })).data
}

export async function withdrawAdProduction(id: number, payload: components['schemas']['EntityDelete']): Promise<AdProduction> {
  return (await api.post<AdProduction>(`/ad-productions/${id}/withdraw`, payload, {
    skipConflictAlert: true, skipForbiddenAlert: true,
  })).data
}

export async function getAdProductionImage(id: number, fileId: number, signal: AbortSignal): Promise<Blob> {
  return (await api.get<Blob>(`/ad-productions/${id}/images/${fileId}`, {
    responseType: 'blob', signal, skipForbiddenAlert: true,
  })).data
}
