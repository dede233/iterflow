import { expect, it } from 'vitest'
import { actionErrorMessage } from './actionError'

it.each([403, 409, 422])('retains the exact business refusal for %i', status => {
  expect(actionErrorMessage({ response: { status, data: { message: '仅对应环节人员可操作; 管理员代操作须填写原因' } } })).toContain('管理员代操作须填写原因')
})
it('distinguishes an unsupported workflow action from invalid form input', () => {
  const error = { response: { status: 422, data: { detail: [{
    type: 'literal_error', loc: ['body', 'action'], input: 'COMPLETE_AND_ACCEPT', msg: 'Internal enum values',
  }] } } }
  expect(actionErrorMessage(error)).toBe('当前服务不支持此流程操作。请刷新页面后重试，若问题仍存在，请联系管理员。原输入已保留。')
})

it.each([
  { detail: [{ type: 'literal_error', loc: ['body', 'requirement_type'], input: 'internal' }] },
  { detail: [{ type: 'string_too_long', loc: ['body', 'reason'], input: 'internal' }] },
  { detail: [null, { type: 'literal_error', loc: ['body', 'action', 'nested'] }] },
  '<html>internal</html>',
])('gives a safe message for other validation failures: %j', data => {
  expect(actionErrorMessage({ response: { status: 422, data } })).toBe('提交内容未通过校验，请检查输入或刷新页面后重试。原输入已保留。')
})

it.each([
  [401, '登录状态已失效'],
  [403, '没有权限'],
  [404, '记录不存在或无法访问'],
  [409, '当前操作存在冲突'],
  [500, '服务器暂时无法处理'],
  [502, '服务器暂时无法处理'],
])('classifies HTTP %i failures even when the response has no business message', (status, message) => {
  const error = { response: { status, data: '<html>Internal server details</html>' } }
  expect(actionErrorMessage(error)).toContain(message)
  expect(actionErrorMessage(error)).not.toContain('Internal server details')
})

it('uses the network message for a network failure', () => {
  expect(actionErrorMessage({ code: 'ERR_NETWORK' })).toContain('请检查网络后重试')
})

it.each([null, {}, new Error('unexpected'), { response: { status: 500, data: { message: 'internal' } } }])('preserves the input hint for unexpected failures: %j', error => {
  expect(actionErrorMessage(error)).toContain('原输入已保留')
})
