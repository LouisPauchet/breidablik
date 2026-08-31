<template>
  <nav class="bottom-nav">
    <NuxtLink v-for="item in items" :key="item.to" :to="item.to" class="nav-item" active-class="active">
      <span class="icon" v-html="item.icon" />
      <span class="label">{{ item.label }}</span>
    </NuxtLink>
  </nav>
</template>

<script setup lang="ts">
const strokeIcon = (paths: string) =>
  `<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">${paths}</svg>`

const items = [
  {
    to: '/',
    label: 'Home',
    icon: strokeIcon(
      '<path d="M3 11.5 12 4l9 7.5" /><path d="M5.5 10v9a1 1 0 0 0 1 1H9.5a1 1 0 0 0 1-1v-4.5h3V19a1 1 0 0 0 1 1h3a1 1 0 0 0 1-1v-9" />'
    ),
  },
  {
    to: '/duties',
    label: 'Duties',
    icon: strokeIcon(
      '<rect x="4.5" y="3.5" width="15" height="17" rx="2" /><path d="M8.5 8h7M8.5 12h7M8.5 16h4" />'
    ),
  },
  {
    to: '/calendar',
    label: 'Calendar',
    icon: strokeIcon(
      '<rect x="3.5" y="5" width="17" height="15.5" rx="2" /><path d="M3.5 9.5h17M8 3v3.5M16 3v3.5" /><path d="M7.5 13.5h2M11 13.5h2M14.5 13.5h2M7.5 17h2M11 17h2" />'
    ),
  },
  {
    to: '/shopping',
    label: 'Shopping',
    icon: strokeIcon(
      '<path d="M4 7h16l-1.4 10.2a2 2 0 0 1-2 1.8H7.4a2 2 0 0 1-2-1.8L4 7Z" /><path d="M8.5 7V6a3.5 3.5 0 0 1 7 0v1" />'
    ),
  },
  {
    to: '/tasks',
    label: 'Tasks',
    icon: strokeIcon(
      '<rect x="4.5" y="4.5" width="15" height="15" rx="3" /><path d="m8.5 12.5 2.3 2.3 4.7-5" />'
    ),
  },
  {
    to: '/profile',
    label: 'Profile',
    icon: strokeIcon('<circle cx="12" cy="8.5" r="3.5" /><path d="M5 20c0-3.6 3.1-6.5 7-6.5s7 2.9 7 6.5" />'),
  },
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
  background: color-mix(in srgb, var(--bg) 90%, transparent);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border-top: 1px solid var(--border);
  padding-bottom: env(safe-area-inset-bottom);
  z-index: 30;
}

.nav-item {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.15rem;
  min-height: 3.75rem;
  padding-top: 0.3rem;
  color: var(--muted);
  text-decoration: none;
  -webkit-tap-highlight-color: transparent;
  transition: color 0.15s ease;
}

.nav-item:active {
  opacity: 0.6;
}

.icon {
  display: flex;
  transition: transform 0.15s ease;
}

.nav-item.active .icon {
  transform: translateY(-1px) scale(1.08);
}

.label {
  font-size: 0.68rem;
  line-height: 1;
}

.nav-item.active {
  color: var(--link);
  font-weight: 600;
}
</style>
