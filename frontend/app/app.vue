<template>
  <div class="app-shell" :class="{ 'full-bleed': route.meta.fullBleed }">
    <main class="app-content">
      <NuxtPage />
    </main>
    <BottomNav v-if="authStore.user && !route.meta.fullBleed" />
    <BirthdayPrompt v-if="!route.meta.fullBleed" />
    <NotificationPrompt v-if="!route.meta.fullBleed" />
  </div>
</template>

<script setup lang="ts">
// Auth state is bootstrapped by app/middleware/auth.global.ts before any page renders,
// not here — avoids two independent code paths racing to initialize the same store.
const authStore = useAuthStore()
const route = useRoute()

// The wall-display dashboard (pages/dashboard/[token].vue) is reached with no login and needs
// the full viewport, not the app's mobile-width column/bottom-nav chrome — it sets this meta
// flag to opt out here rather than every other page needing to know it exists.

// This app redeploys often (see scripts/passenger_update.py). A session left open across a
// deploy is still running the old JS bundle, and its next in-app navigation can try to fetch
// a chunk file that no longer exists on the server (the static build only ever keeps the
// latest hashed files) — Nuxt's fallback for that is a hard reload mid-click. On an iOS
// home-screen PWA, a hard reload is exactly what breaks it out of standalone mode into
// Safari's browser chrome. Proactively reloading here instead — at app-open and whenever the
// app comes back to the foreground, never mid-interaction — means the fresh bundle is
// already in place before the user clicks anything, so that fallback shouldn't get a chance
// to fire in normal use.
onMounted(() => {
  if (!('serviceWorker' in navigator)) return

  let reloaded = false
  navigator.serviceWorker.addEventListener('controllerchange', () => {
    if (reloaded) return
    reloaded = true
    window.location.reload()
  })

  const checkForUpdate = () => {
    navigator.serviceWorker.getRegistration().then((registration) => registration?.update())
  }
  checkForUpdate()
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') checkForUpdate()
  })
})
</script>

<style>
:root {
  color-scheme: light dark;
  --bg: #ffffff;
  --fg: #0f172a;
  --muted: #64748b;
  --accent: #0f766e;
  /* Text/links use --link, not --accent, so dark mode can lighten just this one — --accent
     itself stays a fixed teal because it's also used as a filled-button background with
     white text, which needs it to stay dark enough regardless of page theme. */
  --link: #0f766e;
  --border: #e2e8f0;
}

@media (prefers-color-scheme: dark) {
  :root {
    --bg: #0f172a;
    --fg: #f1f5f9;
    --muted: #94a3b8;
    --border: #1e293b;
    /* #0f766e text on this dark background fails WCAG AA contrast (3.26:1, needs 4.5:1) —
       caught by a Lighthouse audit. A lighter teal keeps the same brand hue at a contrast
       that actually passes. */
    --link: #5eead4;
  }
}

* {
  box-sizing: border-box;
  -webkit-tap-highlight-color: transparent;
}

html,
body,
#__nuxt {
  height: 100%;
  margin: 0;
}

body {
  background: var(--bg);
  color: var(--fg);
  font-family:
    system-ui,
    -apple-system,
    'Segoe UI',
    Roboto,
    sans-serif;
  overscroll-behavior-y: none;
}

.app-shell {
  display: flex;
  flex-direction: column;
  min-height: 100dvh;
}

.app-content {
  flex: 1;
  padding: 1rem;
  padding-top: calc(1rem + env(safe-area-inset-top));
  padding-bottom: calc(4.5rem + env(safe-area-inset-bottom));
  max-width: 640px;
  margin: 0 auto;
  width: 100%;
}

.app-shell.full-bleed .app-content {
  max-width: none;
  padding: 0;
}

/* Native-style press feedback: buttons/links dim briefly on tap instead of
   showing the desktop-oriented default (outline, browser tap-highlight). */
button,
.nav-item,
a {
  touch-action: manipulation;
}

button:active,
a.btn-primary:active,
.card button:active {
  opacity: 0.65;
}

button {
  font-family: inherit;
}

/* Subtle cross-fade between routes so tab switches feel like a native
   view transition rather than an instant content swap. */
.page-enter-active,
.page-leave-active {
  transition:
    opacity 0.16s ease,
    transform 0.16s ease;
}

.page-enter-from {
  opacity: 0;
  transform: translateY(6px);
}

.page-leave-to {
  opacity: 0;
}
</style>
