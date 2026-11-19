export function actionErrorMessage(error: unknown): string {
  const failure = error as { code?: string; response?: { status?: number; data?: { message?: unknown; detail?: unknown } } } | null
  const { status, data } = failure?.response ?? {}
  // Preserve the API's user-facing business messages without exposing validation details.
  if ((status === 403 || status === 409 || status === 422) && typeof data?.message === 'string' && data.message.trim()) {
    return data.message
  }

  const retained = '原输入已保留。'
  switch (status) {
    case 401: return `登录状态已失效，请重新登录。${retained}`
    case 403: return `当前账号没有权限执行此操作。${retained}`
    case 404: return `记录不存在或无法访问，请刷新页面后核对。${retained}`
    case 409: return `当前操作存在冲突，请核对最新记录后重试。${retained}`
    case 422: {
      const details = data?.detail
      if (Array.isArray(details) && details.some(issue => issue?.type === 'literal_error'
        && Array.isArray(issue.loc) && issue.loc.length === 2 && issue.loc[0] === 'body' && issue.loc[1] === 'action')) {
        return `当前服务不支持此流程操作。请刷新页面后重试，若问题仍存在，请联系管理员。${retained}`
      }
      return `提交内容未通过校验，请检查输入或刷新页面后重试。${retained}`
    }
  }
  if (status !== undefined && status >= 500 && status < 600) {
    return `服务器暂时无法处理，请稍后核对最新状态。${retained}`
  }
  if (!failure?.response && failure?.code === 'ERR_NETWORK') {
    return `操作未完成，请检查网络后重试。${retained}`
  }
  return `操作未完成，请稍后重试。${retained}`
}
