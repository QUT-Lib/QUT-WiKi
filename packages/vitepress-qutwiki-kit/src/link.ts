export function safeLink(value?: string): string | undefined {
  if (!value) return undefined
  if (/^(\/|\.\/|\.\.\/|#)/.test(value)) return value.startsWith('//') ? undefined : value
  try {
    const url = new URL(value)
    return url.protocol === 'https:' || url.protocol === 'http:' ? value : undefined
  } catch {
    return undefined
  }
}
