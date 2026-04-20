<!-- CVAlt 是CVAlt 模式下，由引擎对图片分析出边界，给出高亮边界并弹出提示是否确认的组件 -->
<template>
  <div class="cv-alt">
    <div class="cv-alt__prompt">
      <button @click="confirmCvAltPick">确认</button>
      <button @click="reCvAltPick">取消</button>
    </div>
  </div>
</template>
<script setup lang="ts">
import { useCV } from './hooks/useCV'

const { confirmCvAltPick, reCvAltPick } = useCV()

</script>