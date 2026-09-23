type PermissionCheck = (permission: string | string[]) => boolean

export async function loadVersionDetailSections<Requirements, Releases>(
  versionId: number,
  can: PermissionCheck,
  loaders: {
    requirements: (id: number) => Promise<Requirements>
    releases: (id: number) => Promise<Releases>
  },
): Promise<{ requirements: Requirements | null; releases: Releases | null }> {
  const [requirements, releases] = await Promise.all([
    can('rd.requirement.view') ? loaders.requirements(versionId) : Promise.resolve(null),
    can('rd.release.view') ? loaders.releases(versionId) : Promise.resolve(null),
  ])
  return { requirements, releases }
}

export function loadRequirementFeedbackSection<Feedbacks>(
  requirementId: number,
  can: PermissionCheck,
  load: (id: number) => Promise<Feedbacks>,
): Promise<Feedbacks | []> {
  return can('rd.feedback.view') ? load(requirementId) : Promise.resolve([])
}

export function canStartRequirementEditing(can: PermissionCheck): boolean {
  return can('rd.requirement.edit') || can('rd.requirement.status')
}

export function canLinkExistingRequirement(can: PermissionCheck): boolean {
  return can('rd.requirement.view')
}

export async function finishFeedbackConversion(
  requirementId: number,
  can: PermissionCheck,
  navigate: (path: string) => Promise<unknown>,
  reloadFeedback: () => Promise<unknown>,
): Promise<void> {
  if (can('rd.requirement.view')) await navigate(`/requirements/${requirementId}`)
  else await reloadFeedback()
}
