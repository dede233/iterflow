import { describe, expect, it, vi } from 'vitest'
import {
  canLinkExistingRequirement,
  canStartRequirementEditing,
  finishFeedbackConversion,
  loadRequirementFeedbackSection,
  loadVersionDetailSections,
} from './detailAuthorization'
import versionViewSource from '@/views/version/VersionDetailView.vue?raw'
import requirementViewSource from '@/views/requirement/RequirementDetailView.vue?raw'
import feedbackViewSource from '@/views/feedback/FeedbackDetailView.vue?raw'

const permissionSet = (...permissions: string[]) => (permission: string | string[]) => {
  const required = Array.isArray(permission) ? permission : [permission]
  return required.some((code) => permissions.includes(code))
}

describe('detail cross-domain authorization', () => {
  it('loads Version requirements and releases independently by permission', async () => {
    const requirements = vi.fn(async () => ({ items: ['visible'], stats: { total: 1 } }))
    const releases = vi.fn(async () => ['release'])

    const versionOnly = await loadVersionDetailSections(
      7,
      permissionSet('rd.version.view'),
      { requirements, releases },
    )
    expect(versionOnly).toEqual({ requirements: null, releases: null })
    expect(requirements).not.toHaveBeenCalled()
    expect(releases).not.toHaveBeenCalled()

    const releaseReader = await loadVersionDetailSections(
      7,
      permissionSet('rd.version.view', 'rd.release.view'),
      { requirements, releases },
    )
    expect(releaseReader.requirements).toBeNull()
    expect(releaseReader.releases).toEqual(['release'])
    expect(requirements).not.toHaveBeenCalled()
    expect(releases).toHaveBeenCalledOnce()

    const requirementReader = await loadVersionDetailSections(
      7,
      permissionSet('rd.version.view', 'rd.requirement.view'),
      { requirements, releases },
    )
    expect(requirementReader.requirements).toEqual({ items: ['visible'], stats: { total: 1 } })
    expect(requirementReader.releases).toBeNull()
    expect(requirements).toHaveBeenCalledOnce()
    expect(releases).toHaveBeenCalledOnce()
  })

  it('does not request or present linked Feedback without feedback.view', async () => {
    const fetchFeedbacks = vi.fn(async () => ['linked feedback'])
    const result = await loadRequirementFeedbackSection(
      12,
      permissionSet('rd.requirement.view'),
      fetchFeedbacks,
    )
    expect(result).toEqual([])
    expect(fetchFeedbacks).not.toHaveBeenCalled()
    expect(requirementViewSource).toContain('v-if="canViewFeedbacks"')
  })

  it('starts Requirement editing presence only for mutation-capable viewers', () => {
    expect(canStartRequirementEditing(permissionSet('rd.requirement.view'))).toBe(false)
    expect(canStartRequirementEditing(permissionSet('rd.requirement.edit'))).toBe(true)
    expect(canStartRequirementEditing(permissionSet('rd.requirement.status'))).toBe(true)
    expect(requirementViewSource).toContain('canStartRequirementEditing(can)')
  })

  it('allows CREATE_NEW but suppresses LINK_EXISTING for converters without requirement.view', async () => {
    const navigate = vi.fn(async () => undefined)
    const reload = vi.fn(async () => undefined)
    const converterOnly = permissionSet('rd.feedback.convert')
    expect(canLinkExistingRequirement(converterOnly)).toBe(false)
    await finishFeedbackConversion(31, converterOnly, navigate, reload)
    expect(navigate).not.toHaveBeenCalled()
    expect(reload).toHaveBeenCalledOnce()
    expect(feedbackViewSource).toContain('v-if="canLinkExisting"')

    const reader = permissionSet('rd.feedback.convert', 'rd.requirement.view')
    expect(canLinkExistingRequirement(reader)).toBe(true)
    await finishFeedbackConversion(32, reader, navigate, reload)
    expect(navigate).toHaveBeenCalledWith('/requirements/32')
    expect(reload).toHaveBeenCalledOnce()
  })

  it('keeps the Version body independent from hidden cross-domain sections', () => {
    expect(versionViewSource).toContain('item.value = await getVersion(id)')
    expect(versionViewSource).toContain('v-if="canViewRequirements"')
    expect(versionViewSource).toContain('v-if="canViewReleases"')
    expect(versionViewSource).toContain('title="需求清单"')
  })
})
