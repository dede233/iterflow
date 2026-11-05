import { expect, it } from 'vitest'
import { actionErrorMessage } from './actionError'

it.each([403, 409, 422])('retains the exact business refusal for %i', status => {
  expect(actionErrorMessage({ response: { status, data: { message: '仅对应环节人员可操作; 管理员代操作须填写原因' } } })).toContain('管理员代操作须填写原因')
})
it.each([null, {}, new Error('network'), { response: { status: 500, data: { message: 'internal' } } }])('gives a retry message for non-business failures: %j', error => {
  expect(actionErrorMessage(error)).toContain('原输入已保留')
})
