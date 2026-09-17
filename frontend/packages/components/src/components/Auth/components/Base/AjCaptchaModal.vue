<script setup lang="ts">
import { Modal } from 'ant-design-vue'
import { useTranslation } from 'i18next-vue'
import { computed, onBeforeUnmount, ref, watch } from 'vue'

import { checkAjCaptcha, getAjCaptcha } from '../../api/login'
import type { AjCaptchaData, VerificationCodeScene } from '../../interface'
import { buildAjCaptchaPointJson, buildAjCaptchaVerification } from '../../utils/ajCaptchaCrypto'

interface Props {
  open: boolean
  scene: VerificationCodeScene
}

const props = defineProps<Props>()
const emit = defineEmits<{
  cancel: []
  success: [proof: string]
}>()

/** Coordinate space the server renders the puzzle in; drag offsets are scaled back to it. */
const ORIGINAL_IMAGE_WIDTH = 310
const HANDLE_WIDTH = 40
const POINT_Y = 5
const AJ_SUCCESS_CODE = '0000'
const KEYBOARD_STEP = 5
const CLIENT_UID_STORAGE_KEY = 'astron-aj-captcha-client-uid'

const { t } = useTranslation()

const challenge = ref<AjCaptchaData | null>(null)
const dragOffset = ref(0)
const displayedWidth = ref(ORIGINAL_IMAGE_WIDTH)
const loading = ref(false)
const checking = ref(false)
const passed = ref(false)
const errorMessage = ref('')

const barRef = ref<HTMLElement>()
let dragging = false
let activePointerId: number | null = null
let dragStartX = 0
let dragStartOffset = 0
let requestId = 0
let retryTimer: number | null = null
let successTimer: number | null = null

function createRandomUid() {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function')
    return crypto.randomUUID()
  if (typeof crypto !== 'undefined' && typeof crypto.getRandomValues === 'function') {
    const bytes = crypto.getRandomValues(new Uint8Array(16))
    return Array.from(bytes, value => value.toString(16).padStart(2, '0')).join('')
  }
  return `${Date.now()}-${Math.random().toString(36).slice(2)}`
}

/** Correlates this browser session with its captcha challenges; not a credential. */
function resolveClientUid() {
  try {
    const existing = sessionStorage.getItem(CLIENT_UID_STORAGE_KEY)
    if (existing)
      return existing
  }
  catch {
    // Session storage can be unavailable; fall back to an in-memory value.
  }
  const generated = `slider-${createRandomUid()}`
  try {
    sessionStorage.setItem(CLIENT_UID_STORAGE_KEY, generated)
  }
  catch {
    // Ignore: the generated value still works for this dialog instance.
  }
  return generated
}

const clientUid = resolveClientUid()

const maxDragOffset = computed(() => Math.max(0, displayedWidth.value - HANDLE_WIDTH))
const handleDisabled = computed(() => loading.value || checking.value || passed.value || !challenge.value)

const statusText = computed(() => {
  if (loading.value)
    return t('components.auth.ajCaptchaLoading')
  if (checking.value)
    return t('components.auth.ajCaptchaChecking')
  if (passed.value)
    return t('components.auth.ajCaptchaSuccess')
  return t('components.auth.ajCaptchaHint')
})

function clearTimers() {
  if (retryTimer !== null)
    clearTimeout(retryTimer)
  if (successTimer !== null)
    clearTimeout(successTimer)
  retryTimer = null
  successTimer = null
}

function measureWidth() {
  const width = barRef.value?.getBoundingClientRect().width
  if (width)
    displayedWidth.value = width
}

async function loadChallenge() {
  if (retryTimer !== null) {
    clearTimeout(retryTimer)
    retryTimer = null
  }
  const currentRequest = ++requestId
  loading.value = true
  checking.value = false
  passed.value = false
  errorMessage.value = ''
  dragOffset.value = 0
  challenge.value = null
  try {
    const response = await getAjCaptcha(clientUid)
    const data = response?.repData
    if (
      response?.repCode !== AJ_SUCCESS_CODE
      || !data?.originalImageBase64
      || !data.jigsawImageBase64
      || !data.secretKey
      || !data.token
    ) {
      throw new Error(t('components.auth.humanVerificationUnavailable'))
    }
    if (currentRequest === requestId)
      challenge.value = data
  }
  catch (error) {
    if (currentRequest !== requestId)
      return
    errorMessage.value = error instanceof Error && error.message
      ? error.message
      : t('components.auth.humanVerificationUnavailable')
  }
  finally {
    if (currentRequest === requestId)
      loading.value = false
  }
}

async function checkPosition() {
  dragging = false
  activePointerId = null
  const active = challenge.value
  if (dragOffset.value <= 0 || !active?.secretKey || !active.token) {
    dragOffset.value = 0
    return
  }

  // Scale the on-screen offset back into the server's coordinate space.
  const point = {
    x: Math.round((dragOffset.value * ORIGINAL_IMAGE_WIDTH) / displayedWidth.value),
    y: POINT_Y,
  }
  checking.value = true
  errorMessage.value = ''
  try {
    const response = await checkAjCaptcha({
      token: active.token,
      pointJson: buildAjCaptchaPointJson(point, active.secretKey),
      clientUid,
    })
    if (response?.repCode !== AJ_SUCCESS_CODE || response?.repData?.result !== true)
      throw new Error(t('components.auth.ajCaptchaFailed'))

    passed.value = true
    const proof = buildAjCaptchaVerification(active.token, point, active.secretKey)
    // Let the success state render before handing control back.
    successTimer = window.setTimeout(() => emit('success', proof), 300)
  }
  catch (error) {
    errorMessage.value = error instanceof Error && error.message
      ? error.message
      : t('components.auth.ajCaptchaFailed')
    challenge.value = null
    dragOffset.value = 0
    retryTimer = window.setTimeout(() => void loadChallenge(), 700)
  }
  finally {
    checking.value = false
  }
}

function moveDrag(event: PointerEvent) {
  if (!dragging)
    return
  if (activePointerId !== null && event.pointerId !== activePointerId)
    return
  const next = dragStartOffset + event.clientX - dragStartX
  dragOffset.value = Math.min(maxDragOffset.value, Math.max(0, next))
}

function endDrag(event: PointerEvent) {
  if (!dragging)
    return
  if (activePointerId !== null && event.pointerId !== activePointerId)
    return
  void checkPosition()
}

function abortDrag(event?: PointerEvent) {
  if (event && activePointerId !== null && event.pointerId !== activePointerId)
    return
  dragging = false
  activePointerId = null
  dragOffset.value = 0
}

function handleBlur() {
  abortDrag()
}

function bindDragListeners() {
  window.addEventListener('pointermove', moveDrag)
  window.addEventListener('pointerup', endDrag)
  window.addEventListener('pointercancel', abortDrag)
  window.addEventListener('blur', handleBlur)
}

function unbindDragListeners() {
  window.removeEventListener('pointermove', moveDrag)
  window.removeEventListener('pointerup', endDrag)
  window.removeEventListener('pointercancel', abortDrag)
  window.removeEventListener('blur', handleBlur)
}

function startDrag(event: PointerEvent) {
  if (handleDisabled.value)
    return
  if (event.isPrimary === false || (event.pointerType === 'mouse' && event.button !== 0))
    return
  measureWidth()
  dragging = true
  activePointerId = event.pointerId
  dragStartX = event.clientX
  dragStartOffset = dragOffset.value
  event.preventDefault()
}

function handleSliderKeyDown(event: KeyboardEvent) {
  if (handleDisabled.value)
    return
  measureWidth()
  const max = maxDragOffset.value
  if (event.key === 'ArrowLeft')
    dragOffset.value = Math.max(0, dragOffset.value - KEYBOARD_STEP)
  else if (event.key === 'ArrowRight')
    dragOffset.value = Math.min(max, dragOffset.value + KEYBOARD_STEP)
  else if (event.key === 'Home')
    dragOffset.value = 0
  else if (event.key === 'End')
    dragOffset.value = max
  else if (event.key === 'Enter' && dragOffset.value > 0)
    void checkPosition()
  else
    return
  event.preventDefault()
}

function handleModalCancel() {
  if (passed.value)
    return
  emit('cancel')
}

watch(
  () => props.open,
  (open) => {
    if (open) {
      bindDragListeners()
      void loadChallenge()
    }
    else {
      unbindDragListeners()
      requestId += 1
      clearTimers()
      abortDrag()
      challenge.value = null
      errorMessage.value = ''
      passed.value = false
    }
  },
  { immediate: true },
)

onBeforeUnmount(() => {
  unbindDragListeners()
  clearTimers()
})
</script>

<template>
  <Modal
    :open="props.open"
    :footer="null"
    :mask-closable="false"
    :keyboard="!passed"
    :width="360"
    centered
    wrap-class-name="aj-captcha-modal"
    :title="t('components.auth.ajCaptchaTitle')"
    :data-scene="props.scene"
    @cancel="handleModalCancel"
  >
    <div class="aj-captcha-content">
      <div class="aj-captcha-image-panel">
        <img
          v-if="challenge?.originalImageBase64"
          :src="`data:image/png;base64,${challenge.originalImageBase64}`"
          alt=""
          :draggable="false"
          class="aj-captcha-background"
        >
        <div v-else class="aj-captcha-placeholder" />
        <img
          v-if="challenge?.jigsawImageBase64"
          :src="`data:image/png;base64,${challenge.jigsawImageBase64}`"
          alt=""
          :draggable="false"
          class="aj-captcha-puzzle"
          :style="{ transform: `translateX(${dragOffset}px)` }"
        >
        <span class="aj-captcha-watermark" aria-hidden="true">{{ t('app') }}</span>
        <button
          class="aj-captcha-refresh"
          type="button"
          :aria-label="t('components.auth.ajCaptchaRefresh')"
          :disabled="loading || checking || passed"
          @click="loadChallenge"
        >
          &#8635;
        </button>
        <div v-if="errorMessage" class="aj-captcha-error" aria-live="assertive">
          {{ errorMessage }}
        </div>
      </div>
      <div
        ref="barRef"
        class="aj-captcha-bar"
        :class="{ 'is-passed': passed, 'is-checking': checking }"
      >
        <span class="aj-captcha-status" aria-live="polite">{{ statusText }}</span>
        <div class="aj-captcha-progress" :style="{ width: `${dragOffset + HANDLE_WIDTH}px` }" />
        <button
          class="aj-captcha-handle"
          type="button"
          role="slider"
          :aria-label="t('components.auth.ajCaptchaSliderLabel')"
          :aria-valuemin="0"
          :aria-valuemax="Math.round(maxDragOffset)"
          :aria-valuenow="Math.round(dragOffset)"
          :disabled="handleDisabled"
          :style="{ transform: `translateX(${dragOffset}px)` }"
          @pointerdown="startDrag"
          @keydown="handleSliderKeyDown"
        >
          {{ passed ? '✓' : '→' }}
        </button>
      </div>
    </div>
  </Modal>
</template>
