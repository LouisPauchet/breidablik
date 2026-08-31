<template>
  <nav class="bottom-nav">
    <NuxtLink v-for="item in items" :key="item.to" :to="item.to" class="nav-item" active-class="active">
      <span class="label">{{ item.label }}</span>
    </NuxtLink>
  </nav>
</template>

<script setup lang="ts">
const items = [
  { to: '/', label: 'Home' },
  { to: '/duties', label: 'Duties' },
  { to: '/calendar', label: 'Calendar' },
  { to: '/shopping', label: 'Shopping' },
  { to: '/tasks', label: 'Tasks' },
  { to: '/profile', label: 'Profile' },
]
</script>

<style scoped>
.bottom-nav {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  display: flex;
  justify-content: space-around;
  background: var(--bg);
  border-top: 1px solid var(--border);
  padding-bottom: env(safe-area-inset-bottom);
  z-index: 10;
}

.nav-item {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 3.5rem;
  color: var(--muted);
  text-decoration: none;
  font-size: 0.8rem;
}

.nav-item.active {
  color: var(--accent);
  font-weight: 600;
}
</style>
