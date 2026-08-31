<template>
  <header class="page-header">
    <div class="left">
      <NuxtLink v-if="back" :to="back" class="back-btn" aria-label="Back">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
          <path d="M15 18l-6-6 6-6" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" />
        </svg>
      </NuxtLink>
      <h1>{{ title }}</h1>
    </div>
    <div class="actions">
      <slot />
    </div>
  </header>
</template>

<script setup lang="ts">
defineProps<{
  title: string
  back?: string
}>()
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
