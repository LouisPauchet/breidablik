<template>
  <div>
    <h1>Profile</h1>
    <p class="muted">{{ authStore.user?.display_name }} &middot; {{ authStore.user?.email }}</p>

    <h2>Notifications</h2>
    <div class="card">
      <p v-if="!pushSupported" class="muted">Push notifications aren't supported on this browser.</p>
      <template v-else>
        <label class="toggle-row">
          <input type="checkbox" :checked="subscribed" @change="onTogglePush" />
          Get notified when someone adds to a shopping list you're on duty for
        </label>
        <p v-if="pushError" class="error">{{ pushError }}</p>
      </template>
    </div>

    <h3>Recent</h3>
    <p v-if="!notifications.length" class="muted">Nothing yet.</p>
    <ul class="notification-list">
      <li v-for="n in notifications" :key="n.id" :class="{ unread: !n.is_read }" @click="onOpen(n)">
        <div class="notification-title">{{ n.title }}</div>
        <div v-if="n.body" class="muted">{{ n.body }}</div>
      </li>
    </ul>

    <p class="muted future-note">2FA and trusted-device PIN setup are coming soon.</p>
  </div>
</template>

<script setup lang="ts">
interface NotificationItem {
  id: string
  kind: string
  title: string
  body: string | null
  url: string | null
  is_read: boolean
  created_at: string
}

const authStore = useAuthStore()
const push = usePush()
const router = useRouter()

const pushSupported = ref(false)
const subscribed = ref(false)
const pushError = ref('')
const notifications = ref<NotificationItem[]>([])

onMounted(async () => {
  pushSupported.value = push.isSupported()
  if (pushSupported.value) {
    subscribed.value = await push.isSubscribed()
  }
})

notifications.value = await $fetch<NotificationItem[]>('/api/notifications')

async function onTogglePush(event: Event) {
  pushError.value = ''
  const checked = (event.target as HTMLInputElement).checked
  try {
    if (checked) {
      await push.subscribe()
      subscribed.value = true
    } else {
      await push.unsubscribe()
      subscribed.value = false
    }
  } catch (err) {
    pushError.value = err instanceof Error ? err.message : 'Could not update notification settings.'
    ;(event.target as HTMLInputElement).checked = subscribed.value
  }
}

async function onOpen(n: NotificationItem) {
  if (!n.is_read) {
    await $fetch(`/api/notifications/${n.id}/read`, { method: 'POST' })
    n.is_read = true
  }
  if (n.url) await router.push(n.url)
}
</script>

<style scoped>
.muted {
  color: var(--muted);
}

.card {
  border: 1px solid var(--border);
  border-radius: 0.75rem;
  padding: 1rem;
  margin-bottom: 1.5rem;
}

.toggle-row {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  font-size: 0.9rem;
}

.toggle-row input {
  width: auto;
}

.notification-list {
  list-style: none;
  padding: 0;
  margin: 0 0 1.5rem;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.notification-list li {
  border: 1px solid var(--border);
  border-radius: 0.6rem;
  padding: 0.7rem;
  font-size: 0.9rem;
  cursor: pointer;
}

.notification-list li.unread {
  border-color: var(--accent);
}

.notification-title {
  font-weight: 600;
}

.error {
  color: #dc2626;
  font-size: 0.85rem;
}

.future-note {
  font-size: 0.8rem;
}
</style>
