import { message } from 'ant-design-vue'
import i18next from 'i18next'

import type { SendVerificationCodeResult, VerificationCodeScene } from '../interface'

import { toAuthErrorInfo } from './authError'
import { checkRegistered, issueHumanVerificationTicket, sendCaptcha } from './login'

/** Thrown when the user already saw a toast, so callers must not surface a second one. */
export class NotifiedAuthError extends Error {
  retryAfterSeconds?: number

  constructor(msg: string, retryAfterSeconds?: number) {
    super(msg)
    this.name = 'NotifiedAuthError'
    this.retryAfterSeconds = retryAfterSeconds
  }
}

export interface RequestVerificationCodeOptions {
  phone: string
  scene: VerificationCodeScene
  /** false for login / set_password: the phone must already exist. */
  isRegister?: boolean
  /** Runs the slider challenge and resolves with the captcha proof. */
  verifyHuman: () => Promise<string>
}

/**
 * Sending a code takes three server round trips, in this order:
 *   1. human verification (slider) -> proof
 *   2. proof -> one-time ticket bound to phone + scene + client IP
 *   3. ticket -> SMS
 * The server rejects step 3 without a valid ticket, so the order is not optional.
 */
export async function requestVerificationCode({
  phone,
  scene,
  isRegister = true,
  verifyHuman,
}: RequestVerificationCodeOptions): Promise<SendVerificationCodeResult> {
  if (!isRegister) {
    const registered = await checkRegistered({ phone })
    if (!registered) {
      const msg = i18next.t('components.auth.phoneNotRegistered')
      message.warning(msg)
      throw new NotifiedAuthError(msg)
    }
  }

  let captchaProof: string
  try {
    captchaProof = await verifyHuman()
  }
  catch (error) {
    // Cancelling the slider is a normal outcome, so keep the message quiet and specific.
    const msg = error instanceof Error && error.message
      ? error.message
      : i18next.t('components.auth.humanVerificationUnavailable')
    message.warning(msg)
    throw new NotifiedAuthError(msg)
  }

  const { captchaTicket } = await issueHumanVerificationTicket(phone, scene, captchaProof)
  return await sendCaptcha(phone, scene, captchaTicket)
}

/**
 * Resolve the countdown to apply after a failed send. Rate limit responses carry the
 * remaining cooldown, and honouring it keeps the button in sync with the server.
 */
export function resolveRetryAfterSeconds(error: unknown): number | undefined {
  if (error instanceof NotifiedAuthError)
    return error.retryAfterSeconds
  return toAuthErrorInfo(error, '').retryAfterSeconds
}
