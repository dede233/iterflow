import type { components, paths } from './openapi.generated'

type Schema<Name extends keyof components['schemas']> = components['schemas'][Name]
export type Feedback = Schema<'FeedbackOut'>
export type FeedbackPage = Schema<'FeedbackPage'>
export type FeedbackListParams = NonNullable<paths['/feedbacks']['get']['parameters']['query']>
export type FeedbackCreatePayload = Schema<'FeedbackCreate'>
export type PriorityValue = Schema<'Priority'>
export type FeedbackUpdatePayload = Schema<'FeedbackUpdate'>
export type FeedbackStatusChangePayload = Schema<'FeedbackStatusChange'>
export type ConvertFeedbackPayload = Schema<'FeedbackConvertRequest'>

export type SystemsResponse = Schema<'BusinessSystemCatalogOut'>
export type BusinessSystemItem = SystemsResponse['systems'][number]
export type BusinessModuleItem = SystemsResponse['modules'][number]
export type AttachmentItem = Schema<'AttachmentOut'>
export type CommentItem = Schema<'CommentOut'>

export type Requirement = Schema<'RequirementOut'>
export type RequirementPage = Schema<'RequirementPage'>
export type RequirementCreatePayload = Schema<'RequirementCreate'>
export type RequirementUpdatePayload = Schema<'RequirementUpdate'>
export type RequirementStatusChangePayload = Schema<'RequirementStatusChange'>
export type LinkedFeedback = Schema<'LinkedFeedbackOut'>

export type VersionItem = Schema<'VersionOut'>
export type VersionPage = Schema<'VersionPage'>
export type VersionCreatePayload = Schema<'VersionCreate'>
export type VersionUpdatePayload = Schema<'VersionUpdate'>
export type VersionStatusChangePayload = Schema<'VersionStatusChange'>
export type VersionStats = Schema<'VersionStats'>
export type VersionRequirementsResult = Schema<'VersionRequirementsOut'>
export type AddRequirementPayload = Schema<'AddRequirementRequest'>
export type RemoveRequirementPayload = Schema<'RemoveRequirementRequest'>
export type MoveRequirementPayload = Schema<'MoveRequirementRequest'>
export type PublishCheckItem = Schema<'PublishCheckItem'>
export type PublishCheckResult = Schema<'PublishCheckResult'>
export type PublishResult = Schema<'PublishResult'>

export type ReleaseItem = Schema<'ReleaseOut'>
export type ReleasePage = Schema<'ReleasePage'>
export type AuditOperator = Schema<'AuditOperatorOut'>
export type AuditItem = Schema<'AuditOut'>
export type AuditListParams = NonNullable<paths['/audits']['get']['parameters']['query']>
export type AuditPage = Schema<'AuditPage'>
export type NotificationItem = Schema<'NotificationOut'>
