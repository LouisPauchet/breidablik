<template>
  <div class="app-shell">
    <main class="app-content">
      <NuxtPage />
    </main>
    <BottomNav v-if="authStore.user" />
    <BirthdayPrompt />
  </div>
</template>

<script setup lang="ts">
// Auth state is bootstrapped by app/middleware/auth.global.ts before any page renders,
// not here — avoids two independent code paths racing to initialize the same store.
const authStore = useAuthStore()
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
}

.app-shell {
  display: flex;
  flex-direction: column;
  min-height: 100dvh;
}

.app-content {
  flex: 1;
  padding: 1rem;
  padding-bottom: calc(4.5rem + env(safe-area-inset-bottom));
  max-width: 640px;
  margin: 0 auto;
  width: 100%;
}
</style>
