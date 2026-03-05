<template>
  <el-space wrap>
    <el-tag v-for="a in list" :key="a" size="small">{{ a }}</el-tag>
    <el-tag v-if="list.length === 0" size="small" type="info">未知</el-tag>
  </el-space>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  /** Accepts string[], { name: string }[], comma-string, or a meta object with .authors/.author */
  authors?: string[] | string | { name: string }[] | Record<string, any> | null
}>()

const list = computed<string[]>(() => {
  const a = props.authors
  if (!a) return []
  if (Array.isArray(a)) {
    return (a as any[]).map(x => (typeof x === 'string' ? x : x?.name || String(x))).filter(Boolean)
  }
  if (typeof a === 'string') return a ? [a] : []
  return []
})
</script>
