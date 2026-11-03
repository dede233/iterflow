// The API sends user-facing business messages; render them as text in the form.
export function actionErrorMessage(error: unknown): string {
  const response = (error as { response?: { status?: number; data?: { message?: unknown } } })?.response
  if ([403, 409, 422].includes(response?.status ?? 0) && typeof response?.data?.message === 'string') return response.data.message
  return '操作未完成，请检查网络后重试；原输入已保留。'
}
