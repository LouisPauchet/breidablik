<template>
  <div v-if="show" class="sheet">
    <div class="sheet-body">
      <strong>Turn on notifications?</strong>
      <p class="muted">Get notified when someone adds to a shopping list you're on duty for.</p>
      <div class="actions">
        <button type="button" class="primary" @click="onEnable">Enable</button>
        <button type="button" class="secondary" @click="onDismiss">Not now</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
const authStore = useAuthStore()
const push = usePush()

const blockingPromptOpen = useState<boolean>('blockingPromptOpen', () => false)

const supported = ref(false)
const alreadyDecided = ref(true) // avoids a flash before the checks below resolve
const dismissedThisDevice = ref(true)

onMounted(async () => {
  supported.value = push.isSupported()
  if (supported.value) {
    const subscribed = await push.isSubscribed()
    alreadyDecided.value = subscribed || (typeof Notification !== 'undefined' && Notification.permission !== 'default')
  }
  try {
    dismissedThisDevice.value = localStorage.getItem('notificationPromptDismissed') === '1'
  } catch {
    // Storage can be unavailable (private browsing, blocked site data) — treat as not
    // dismissed rather than blocking the prompt from ever showing on this device.
    dismissedThisDevice.value = false
  }
})

const show = computed(
  () =>
    !!authStore.user &&
    supported.value &&
    !alreadyDecided.value &&
    !dismissedThisDevice.value &&
    !blockingPromptOpen.value
)

function remember() {
  dismissedThisDevice.value = true
  try {
    localStorage.setItem('notificationPromptDismissed', '1')
  } catch {
    // Best effort — if storage isn't available the prompt may show again next visit,
    // which is harmless.
  }
}

async function onEnable() {
  try {
    await push.subscribe()
  } catch {
    // The browser's own permission dialog may have been denied, or push isn't configured
    // on the server — either way there's nothing actionable to show here, just stop asking.
  }
  alreadyDecided.value = true
  remember()
}

function onDismiss() {
  remember()
}
</script>

<style scoped>
.sheet {
  position: fixed;
  left: 1rem;
  right: 1rem;
  bottom: calc(4.5rem + env(safe-area-inset-bottom) + 0.75rem);
  z-index: 40;
  max-width: 600px;
  margin: 0 auto;
}

.sheet-body {
  background: var(--bg);
  color: var(--fg);
  border: 1px solid var(--border);
  border-radius: 0.85rem;
  padding: 1rem;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.18);
}

.muted {
  color: var(--muted);
  font-size: 0.85rem;
  margin: 0.35rem 0 0.85rem;
}

.actions {
  display: flex;
  gap: 0.5rem;
}

.actions button {
  flex: 1;
  padding: 0.55rem;
  border-radius: 0.5rem;
  font-size: 0.9rem;
}

.actions .primary {
  border: none;
  background: var(--accent);
  color: white;
}

.actions .secondary {
  border: 1px solid var(--border);
  background: var(--bg);
  color: var(--fg);
}
</style>
