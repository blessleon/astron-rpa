<script setup lang="ts">
import { Button, Input, message } from 'ant-design-vue'
import type { FormInstance } from 'ant-design-vue'
import { useTranslation } from 'i18next-vue'
import { computed, onBeforeUnmount, ref } from 'vue'

import { resolveRetryAfterSeconds } from '../../api/requestVerificationCode'
import type { SendVerificationCodeResult, VerificationCodeScene } from '../../interface'

import AjCaptchaModal from './AjCaptchaModal.vue'

interface Props {
  modelValue?: string
  placeholder?: string
  maxlength?: number
  codeLength?: number
  countdownSeconds?: number
  disabled?: boolean
  wrapRef?: FormInstance | undefined
  relationKey?: string
  scene?: VerificationCodeScene
  sendCaptcha?: (phone: string, verifyHuman: () => Promise<string>) => Promise<SendVerificationCodeResult | void>
}

const props = withDefaults(defineProps<Props>(), {
  modelValue: '',
  maxlength: 6,
  countdownSeconds: 60,
  scene: 'login',
})
const emit = defineEmits<{
  'update:modelValue': [value: string]
  'send': []
}>()
const { t } = useTranslation()
const captcha = ref(props.modelValue || '')
const countdown = ref(0)
const isCodeSending = ref(false)
let countdownTimer: number | null = null

const captchaModalOpen = ref(false)
let pendingVerification: { resolve: (proof: string) => void, reject: (error: Error) => void } | null = null

/** Turns the slider dialog into an awaitable step of the send flow. */
function verifyHuman(): Promise<string> {
  settleVerification(request => request.reject(new Error(t('components.auth.humanVerificationCancelled'))))
  return new Promise<string>((resolve, reject) => {
    pendingVerification = { resolve, reject }
    captchaModalOpen.value = true
  })
}

function settleVerification(settle: (request: NonNullable<typeof pendingVerification>) => void) {
  const request = pendingVerification
  pendingVerification = null
  captchaModalOpen.value = false
  if (request)
    settle(request)
}

function handleCaptchaSuccess(proof: string) {
  settleVerification(request => request.resolve(proof))
}

function handleCaptchaCancel() {
  settleVerification(request => request.reject(new Error(t('components.auth.humanVerificationCancelled'))))
}

const placeholderText = computed(() => props.placeholder || t('components.auth.enterCaptcha'))

// 验证码按钮文本
const codeButtonText = computed(() => {
  if (countdown.value > 0) {
    return t('components.auth.captchaSent', { seconds: countdown.value })
  }
  if (isCodeSending.value) {
    return t('components.auth.sending')
  }
  return t('components.auth.sendCaptcha')
})

// 验证码按钮是否禁用
const codeButtonDisabled = computed(() => {
  return isCodeSending.value || countdown.value > 0 || props.disabled
})

// 发送验证码
async function handleSendCode() {
  if (codeButtonDisabled.value)
    return
  isCodeSending.value = true
  try {
    await props.wrapRef?.validateFields([props.relationKey || 'phone'])
    const phone = props.wrapRef?.getFieldsValue()[props.relationKey || 'phone']
    if (!props.sendCaptcha)
      throw new Error(t('components.auth.sendCaptchaUndefined'))

    const result = await props.sendCaptcha(phone, verifyHuman)
    startCountdown(result?.retryAfterSeconds)
    message.success(t('components.auth.captchaSendSuccess'))
  }
  catch (e) {
    // The request layer already surfaced a message; only sync the cooldown here so a
    // rate-limited retry does not look available before the server allows it.
    const retryAfterSeconds = resolveRetryAfterSeconds(e)
    if (retryAfterSeconds)
      startCountdown(retryAfterSeconds)
    console.log(e)
  }
  finally {
    isCodeSending.value = false
    settleVerification(request => request.reject(new Error(t('components.auth.humanVerificationCancelled'))))
  }
}

// 开始倒计时，优先采用服务端返回的冷却秒数
function startCountdown(seconds?: number) {
  if (countdownTimer)
    clearInterval(countdownTimer)

  countdown.value = Math.max(1, seconds || props.countdownSeconds)
  countdownTimer = window.setInterval(() => {
    countdown.value--
    if (countdown.value <= 0) {
      if (countdownTimer)
        clearInterval(countdownTimer)
      countdownTimer = null
    }
  }, 1000)
}

// 清空倒计时
function clearCountdown() {
  if (countdownTimer) {
    clearInterval(countdownTimer)
    countdownTimer = null
  }
  countdown.value = 0
}

// 更新值
function handleInput(value: string) {
  captcha.value = value
  emit('update:modelValue', captcha.value)
}

function trimInput(e: Event) {
  captcha.value = (e.target as HTMLInputElement).value.trim()
  emit('update:modelValue', captcha.value)
}

// 清空表单
function resetForm() {
  captcha.value = ''
  clearCountdown()
  isCodeSending.value = false
  settleVerification(request => request.reject(new Error(t('components.auth.humanVerificationCancelled'))))
}

// 暴露方法
defineExpose({
  resetForm,
  startCountdown,
  clearCountdown,
})

onBeforeUnmount(() => {
  clearCountdown()
  settleVerification(request => request.reject(new Error(t('components.auth.humanVerificationCancelled'))))
})
</script>

<template>
  <div class="captcha-input-wrapper">
    <Input
      :value="captcha"
      :placeholder="placeholderText"
      :maxlength="props.maxlength"
      :disabled="props.disabled"
      size="large"
      @input="(e) => handleInput(e.target.value ?? '')"
      @blur="trimInput"
    />
    <Button size="large" type="link" class="absolute !w-auto !h-auto !m-0 !p-0 right-[10px] top-[7px] !text-[14px] text-[#000000D9] dark:text-[#FFFFFFD9]" :disabled="codeButtonDisabled" @click="handleSendCode">
      {{ codeButtonText }}
    </Button>
    <AjCaptchaModal
      :open="captchaModalOpen"
      :scene="props.scene"
      @success="handleCaptchaSuccess"
      @cancel="handleCaptchaCancel"
    />
  </div>
</template>

<style scoped>
.captcha-input-wrapper {
  width: 100%;
}
</style>
