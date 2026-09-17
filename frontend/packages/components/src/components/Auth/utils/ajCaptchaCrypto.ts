import CryptoJS from 'crypto-js'

export interface AjCaptchaPoint {
  x: number
  y: number
}

/**
 * AJ-Captcha requires AES-ECB encryption with the per-challenge secretKey.
 * The cipher mode is dictated by the server protocol and cannot be changed here.
 */
export function encryptAjCaptcha(value: string, secretKey: string): string {
  const key = CryptoJS.enc.Utf8.parse(secretKey)
  const payload = CryptoJS.enc.Utf8.parse(value)
  return CryptoJS.AES.encrypt(payload, key, {
    mode: CryptoJS.mode.ECB,
    padding: CryptoJS.pad.Pkcs7,
  }).toString()
}

/** Payload for the captcha/check request. */
export function buildAjCaptchaPointJson(point: AjCaptchaPoint, secretKey: string): string {
  return encryptAjCaptcha(JSON.stringify(point), secretKey)
}

/** Proof exchanged for a one-time verification ticket after the slider passes. */
export function buildAjCaptchaVerification(token: string, point: AjCaptchaPoint, secretKey: string): string {
  return encryptAjCaptcha(`${token}---${JSON.stringify(point)}`, secretKey)
}
