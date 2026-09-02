<template>
  <div class="avatar-wrap" :style="{ width: `${size}px`, height: `${size}px` }">
    <div class="avatar">
      <img v-if="src && !failed" :src="src" :alt="name" @error="failed = true" />
      <span v-else class="initials" :style="{ background: bgColor, fontSize: `${fontSize}px` }">{{ initials }}</span>
    </div>
    <span v-if="badge" class="badge" :style="{ fontSize: `${badgeFontSize}px` }">{{ badge }}</span>
  </div>
</template>

<script setup lang="ts">
const props = withDefaults(
  defineProps<{
    userId: string
    name: string
    avatarUpdatedAt?: string | null
    size?: number
    srcOverride?: string | null
    badge?: string | null
  }>(),
  { size: 32, avatarUpdatedAt: null, srcOverride: null, badge: null }
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
  if (props.srcOverride) return props.srcOverride
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
const badgeFontSize = computed(() => Math.max(10, Math.round(props.size * 0.5)))
</script>

<style scoped>
.avatar-wrap {
  position: relative;
  display: inline-flex;
  flex-shrink: 0;
}

.avatar {
  width: 100%;
  height: 100%;
  border-radius: 999px;
  overflow: hidden;
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

.badge {
  position: absolute;
  right: -2px;
  bottom: -2px;
  line-height: 1;
  background: var(--bg);
  border-radius: 999px;
  padding: 1px;
  box-shadow: 0 0 0 1px var(--border);
}
</style>
