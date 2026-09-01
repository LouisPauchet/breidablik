<template>
  <header class="page-header">
    <div class="left">
      <button v-if="back" type="button" class="back-btn" aria-label="Back" @click="onBack">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
          <path d="M15 18l-6-6 6-6" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" />
        </svg>
      </button>
      <h1>{{ title }}</h1>
    </div>
    <div class="actions">
      <slot />
    </div>
  </header>
</template>

<script setup lang="ts">
const props = defineProps<{
  title: string
  // Fallback destination used only when there's no actual in-app history to go back to
  // (e.g. this page was opened directly, or is the first screen visited this session) —
  // otherwise back navigates to wherever the user actually came from.
  back?: string
}>()

const router = useRouter()

function onBack() {
  if (typeof window !== 'undefined' && window.history.state?.back) {
    router.back()
  } else if (props.back) {
    router.push(props.back)
  }
}
</script>

<style scoped>
.page-header {
  position: sticky;
  top: 0;
  z-index: 20;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  margin: calc(-1rem - env(safe-area-inset-top)) -1rem 1rem;
  padding: calc(0.65rem + env(safe-area-inset-top)) 1rem 0.65rem;
  background: color-mix(in srgb, var(--bg) 88%, transparent);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border-bottom: 1px solid var(--border);
}

.left {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  min-width: 0;
}

h1 {
  font-size: 1.4rem;
  margin: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.back-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 2.25rem;
  height: 2.25rem;
  margin-left: -0.4rem;
  border: none;
  background: none;
  border-radius: 999px;
  color: var(--link);
  flex-shrink: 0;
}

.back-btn:active {
  background: var(--border);
}

.actions {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-shrink: 0;
}
</style>
