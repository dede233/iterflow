import { describe, expect, it } from 'vitest'
import {
  auditActionLabel,
  auditActionOptions,
  auditEntityLabel,
  auditEntityOptions,
} from './auditLabels'

describe('audit display labels', () => {
  it('maps saved audit codes to Chinese without changing filter values', () => {
    expect(auditEntityLabel('REQUIREMENT')).toBe('需求')
    expect(auditEntityLabel('BUSINESS_MODULE')).toBe('业务模块')
    expect(auditActionLabel('STATUS_CHANGE')).toBe('变更状态')
    expect(auditActionLabel('MODULE_CREATE')).toBe('创建业务模块')
    expect(auditEntityOptions.find((item) => item.label === '需求')?.value).toBe('REQUIREMENT')
    expect(auditActionOptions.find((item) => item.label === '变更状态')?.value).toBe('STATUS_CHANGE')
  })

  it('keeps unfamiliar codes visible for diagnosis', () => {
    expect(auditEntityLabel('FUTURE_ENTITY')).toBe('未知实体（FUTURE_ENTITY）')
    expect(auditActionLabel('FUTURE_ACTION')).toBe('未知操作（FUTURE_ACTION）')
  })
})
