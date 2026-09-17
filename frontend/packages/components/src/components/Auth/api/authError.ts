/** Rate limit code returned by /verification-code/send. */
export const SMS_RATE_LIMITED_CODE = '600005'

export interface AuthErrorInfo {
  code?: string
  message: string
  retryAfterSeconds?: number
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

function positiveSeconds(value: unknown): number | undefined {
  const parsed = typeof value === 'string' ? Number(value) : value
  if (typeof parsed !== 'number' || !Number.isFinite(parsed) || parsed <= 0)
    return undefined
  return Math.ceil(parsed)
}

/**
 * The rate limit message carries the cooldown in prose ("请60秒后再试" / "retry after 60 seconds"),
 * so parse it as a fallback when the server omits a structured retryAfterSeconds.
 */
function retryAfterFromMessage(code: string | undefined, message: string): number | undefined {
  if (code !== SMS_RATE_LIMITED_CODE)
    return undefined
  const match = message.match(/(\d+)\s*(?:秒|seconds?)/i)
  return match ? positiveSeconds(match[1]) : undefined
}

/**
 * `request()` rejects with the raw response body on a non-success code, or with an
 * axios error on transport failure. Normalise both into something callers can branch on.
 */
export function toAuthErrorInfo(error: unknown, fallbackMessage: string): AuthErrorInfo {
  if (!isRecord(error))
    return { message: fallbackMessage }

  const code = typeof error.code === 'string' ? error.code : undefined
  const message
    = (typeof error.message === 'string' && error.message)
      || (typeof error.msg === 'string' && error.msg)
      || fallbackMessage

  const data = isRecord(error.data) ? error.data : undefined
  const retryAfterSeconds
    = positiveSeconds(error.retryAfterSeconds)
      || positiveSeconds(data?.retryAfterSeconds)
      || retryAfterFromMessage(code, message)

  return { code, message, retryAfterSeconds }
}
