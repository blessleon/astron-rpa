<!-- @format -->

<script lang="ts" setup>
// import ConfigProvider from '@/components/ConfigProvider/index.vue'
import { useHighlight } from './hooks/useHighlight'
import CV from './CV.vue'
import { PickMode } from './config'
import { currentLocale, t } from './locale'

const {
  mousePos,
  pickMode,
  tooltipVisible,
  tooltipPos,
  tagPosition,
  shortcuts,
  cvCropShow,
  pickStep,
  highlightRects,
  targetRect,
  targetRectShow,
  targetButton,
  confirmCvCtrlPick,
  confirmCvAltPick,
  sendScreenshot,
  reCvAltPick,
  captureDone,
} = useHighlight()

</script>

<template>
    <div class="highlight-overlay">
      <div :class="`highlight-area  ${pickMode === PickMode.VALIDATE ? 'highlight-area-validate' : ''}`">
        <div
          v-for="(rect, index) in highlightRects"
          :key="index"
          :class="`highlight-box ${pickMode === PickMode.VALIDATE ? 'highlight-box-validate' : ''}`"
          :style="{
            transform: `translate(${rect.x}px, ${rect.y}px)`,
            width: rect.width + 'px',
            height: rect.height + 'px',
          }"
        >
          <div v-if="rect.tag" :class="`highlight-tag highlight-tag-${tagPosition}`">{{ rect.tag }}</div>
        </div>
      </div>

      <CV
        v-if="cvCropShow"
        :cvStep="pickStep"
        :targetRect="targetRect"
        :targetRectShow="targetRectShow"
        :targetButton="targetButton"
        :pickMode="pickMode"
        @save="confirmCvCtrlPick"
        @confirm-alt="confirmCvAltPick"
        @send-screenshot="sendScreenshot"
        @reselect-alt="reCvAltPick"
        @capture-done="captureDone"
      />

      <div v-if="tooltipVisible" :class="`tooltip bg-bg-elevated ${tooltipPos === 'leftTop' ? 'tooltip-left-top' : 'tooltip-right-bottom'}`">
        <div class="tooltip-item font-bold" v-for="(sc, i) in shortcuts" :key="i">
          <span :class="`short-title ${currentLocale === 'en_US' ? 'short-title-en':''}`" >{{ sc.title }}</span>
          <span class="short-keys">{{ sc.keys }}</span>
        </div>
        <div class="tooltip-item">
          <span :class="`short-title ${currentLocale === 'en_US' ? 'short-title-en':''}`">{{ t('position') }}</span>
          <span class="short-xy">{{ mousePos.x }},{{ mousePos.y }}</span>
        </div>
      </div>
    </div>
</template>

<style lang="scss">
.highlight-overlay {
  width: 100vw;
  height: 100%;
  position: fixed;
  top: 0;
  left: 0;
  background: transparent;
}


.highlight-box {
  position: absolute;
  border: 2px solid var(--color-primary);
  background: #716fff28;
  pointer-events: none;
  transition: all 0.01s ease-out;
  border-radius: 4px;
  z-index: 99999;
  .highlight-tag {
    position: absolute;
    background: #1c1c1c;
    color: #fff;
    padding: 2px 6px;
    font-size: 12px;
    border-radius: 4px;
    white-space: nowrap;
   transition: all 0.01s ease-out;

    &-top {
      top: -26px;
      left: -2px;
    }

    &-bottom {
      bottom: -26px;
      left: -2px;
    }
  }
}

.highlight-box-validate {
  transition: none;
}

.highlight-area {
  pointer-events: none;
}

.highlight-area-validate {
  opacity: 0;
  animation: validatePulse 0.5s infinite;
}

@keyframes validatePulse {
  0% {
    opacity: 0;
  }

  50% {
    opacity: 1;
  }

  100% {
    opacity: 0;
  }
}

.tooltip {
  position: fixed;
  // background: var(--color-bg-elevated);
  padding: 8px 12px;
  border-radius: 4px;
  font-size: 12px;
  line-height: 1.5;
  pointer-events: none;
  border: 1px var(--color-border) solid;
  width: 190px;

  &-left-top {
    top: 10px;
    left: 10px;
  }

  &-right-bottom {
    bottom: 60px;
    right: 10px;
  }

  .tooltip-item {
    margin-bottom: 4px;
    display: flex;
    align-items: center;

    &:last-child {
      margin-bottom: 0;
    }

    .short-title {
      margin-right: 6px;
      width: 58px;
      display: inline-block;
    }
    .short-title-en {
      margin-right: 6px;
      width: 128px;
      display: inline-block;
    }

    .short-keys {
      background: var(--color-border-secondary);
      padding: 4px;
      border-radius: 3px;
      font-size: 12px;
      border: 1px solid var(--color-border);
      line-height: 1;
    }
  }
}
</style>
