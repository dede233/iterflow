import { api } from './client'
import type { components } from '@/types/openapi.generated'

export type WecomPreferences = components['schemas']['WecomPreferencesOut']
export type WecomMode = WecomPreferences['mode']
type PreferenceChange = components['schemas']['WecomPreferenceChange']
type BindingChange = components['schemas']['WecomBindingChange']

const inlineErrors = { skipConflictAlert: true, skipForbiddenAlert: true }

export const getWecomPreferences = () =>
  api.get<WecomPreferences>('/me/wecom-preferences').then(({ data }) => data)

export const updateWecomPreferences = (payload: PreferenceChange) =>
  api.put<WecomPreferences>('/me/wecom-preferences', payload, inlineErrors).then(({ data }) => data)

export const getUserWecomBinding = (userId: number) =>
  api.get<WecomPreferences>(`/users/${userId}/wecom-binding`, inlineErrors).then(({ data }) => data)

export const updateUserWecomBinding = (userId: number, payload: BindingChange) =>
  api.put<WecomPreferences>(`/users/${userId}/wecom-binding`, payload, inlineErrors).then(({ data }) => data)
