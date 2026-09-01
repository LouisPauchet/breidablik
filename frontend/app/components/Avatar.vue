<template>
  <div class="avatar" :style="{ width: `${size}px`, height: `${size}px`, fontSize: `${fontSize}px` }">
    <img v-if="src && !failed" :src="src" :alt="name" @error="failed = true" />
    <span v-else class="initials" :style="{ background: bgColor }">{{ initials }}</span>
  </div>
</template>

<script setup lang="ts">
const props = withDefaults(
  defineProps<{
    userId: string
    name: string
    avatarUpdatedAt?: string | null
    size?: number
  }>(),
  { size: 32, avatarUpdatedAt: null }
)

const failed = ref(false)
watch(
  () => props.avatarUpdatedAt,
  () => {
    failed.value = false
  }
)

const src = computed(() => {
  if (!props.avatarUpdatedAt) return null
  return `/api/users/${props.userId}/avatar?v=${encodeURIComponent(props.avatarUpdatedAt)}`
})

const initials = computed(() => {
  const parts = props.name.trim().split(/\s+/).filter(Boolean)
  if (!parts.length) return '?'
  if (parts.length === 1) return parts[0]!.slice(0, 2).toUpperCase()
  return (parts[0]![0] + parts[parts.length - 1]![0]).toUpperCase()
})

// Deterministic per-user color so the same person's initials avatar always looks the same,
// without needing to store a color choice anywhere.
const PALETTE = ['#0f766e', '#2563eb', '#9333ea', '#d97706', '#db2777', '#059669', '#dc2626', '#4f46e5']
const bgColor = computed(() => {
  let hash = 0
  for (const ch of props.userId) hash = (hash * 31 + ch.charCodeAt(0)) >>> 0
  return PALETTE[hash % PALETTE.length]
})

const fontSize = computed(() => Math.round(props.size * 0.4))
</script>

<style scoped>
.avatar {
  border-radius: 999px;
  overflow: hidden;
  flex-shrink: 0;
  display: inline-flex;
}

.avatar img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.initials {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-weight: 600;
  letter-spacing: -0.02em;
}
</style>
