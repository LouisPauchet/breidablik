<template>
  <div>
    <h1>Profile</h1>
    <p class="muted">{{ authStore.user?.display_name }} &middot; {{ authStore.user?.email }}</p>

    <h2>Birthday</h2>
    <div class="card">
      <label>
        <input v-model="birthdayDraft" type="date" :max="todayIso" />
      </label>
      <p v-if="birthdayError" class="error">{{ birthdayError }}</p>
      <button
        type="button"
        :disabled="!birthdayDraft || birthdayDraft === authStore.user?.birthday"
        @click="onSaveBirthday"
      >
        Save
      </button>
    </div>

    <h2>Security</h2>
    <div class="card">
      <h3>Two-factor authentication</h3>

      <template v-if="totpStep === 'idle'">
        <p v-if="authStore.user?.is_2fa_enabled" class="status-ok">Enabled</p>
        <template v-else>
          <p class="muted">Not enabled.</p>
          <button type="button" @click="onStartTotp">Enable 2FA</button>
        </template>

        <template v-if="authStore.user?.is_2fa_enabled">
          <button type="button" class="link-btn" @click="show2faDisableForm = !show2faDisableForm">
            Disable 2FA
          </button>
          <div v-if="show2faDisableForm" class="inline-form">
            <input v-model="disable2faPassword" type="password" placeholder="Confirm your password" />
            <button type="button" @click="onDisableTotp">Confirm disable</button>
          </div>
          <p v-if="disable2faError" class="error">{{ disable2faError }}</p>
        </template>
      </template>

      <div v-else-if="totpStep === 'enrolling'" class="totp-enroll">
        <p class="muted">Scan this with your authenticator app:</p>
        <img :src="totpQrDataUri" alt="TOTP QR code" class="qr-image" />
        <p class="muted small">Or enter manually: <code>{{ totpSecret }}</code></p>
        <label>
          Code from your app
          <input v-model="totpCode" inputmode="numeric" autocomplete="one-time-code" />
        </label>
        <p v-if="totpError" class="error">{{ totpError }}</p>
        <div class="btn-row">
          <button type="button" @click="onConfirmTotp">Confirm</button>
          <button type="button" class="secondary-btn" @click="onCancelTotp">Cancel</button>
        </div>
      </div>

      <div v-else class="recovery-codes">
        <p>
          <strong>Save these recovery codes somewhere safe.</strong> Each works once if you
          lose access to your authenticator app. They won't be shown again.
        </p>
        <ul>
          <li v-for="code in recoveryCodes" :key="code"><code>{{ code }}</code></li>
        </ul>
        <button type="button" @click="totpStep = 'idle'">I've saved these</button>
      </div>
    </div>

    <div class="card">
      <h3>Quick PIN unlock on this device</h3>
      <template v-if="deviceTrust.trusted">
        <p class="status-ok">
          Set up{{ deviceTrust.device_label ? ` (${deviceTrust.device_label})` : '' }}
        </p>
        <button type="button" @click="onForgetDevice">Forget this device</button>
      </template>
      <template v-else>
        <p class="muted">
          Skip password{{ authStore.user?.is_2fa_enabled ? ' + 2FA' : '' }} next time you log in
          on this device.
        </p>
        <label>
          PIN (4+ characters)
          <input v-model="newPin" type="password" inputmode="numeric" autocomplete="off" />
        </label>
        <label>
          Confirm PIN
          <input v-model="confirmPin" type="password" inputmode="numeric" autocomplete="off" />
        </label>
        <label>
          Label (optional)
          <input v-model="deviceLabel" placeholder="e.g. Kitchen tablet" />
        </label>
        <p v-if="pinError" class="error">{{ pinError }}</p>
        <button type="button" @click="onSetupPin">Set up PIN</button>
      </template>
    </div>

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

    <h2>Subscribe to your calendar</h2>
    <div class="card">
      <p class="muted">
        Add this link in Google/Apple/Outlook calendar as a URL subscription to see your
        duties, tasks, all household events, and everyone's away dates.
      </p>
      <div class="feed-row">
        <input :value="feedUrl" readonly @focus="($event.target as HTMLInputElement).select()" />
        <button type="button" @click="onCopyFeedUrl">{{ copied ? 'Copied!' : 'Copy' }}</button>
      </div>
      <button type="button" class="link-btn" @click="onRegenerateFeed">
        Regenerate link (if it ever leaks)
      </button>
    </div>

    <NuxtLink v-if="authStore.user?.is_superuser" to="/admin/members" class="admin-link">
      Manage members &rarr;
    </NuxtLink>
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

interface DeviceTrustStatus {
  trusted: boolean
  device_label?: string | null
}

const authStore = useAuthStore()
const push = usePush()
const router = useRouter()

const pushSupported = ref(false)
const subscribed = ref(false)
const pushError = ref('')
const notifications = ref<NotificationItem[]>([])
const copied = ref(false)

const todayIso = new Date().toISOString().slice(0, 10)
const birthdayDraft = ref(authStore.user?.birthday ?? '')
const birthdayError = ref('')

const totpStep = ref<'idle' | 'enrolling' | 'recovery-codes'>('idle')
const totpQrDataUri = ref('')
const totpSecret = ref('')
const totpCode = ref('')
const totpError = ref('')
const recoveryCodes = ref<string[]>([])
const show2faDisableForm = ref(false)
const disable2faPassword = ref('')
const disable2faError = ref('')

const deviceTrust = ref<DeviceTrustStatus>({ trusted: false })
const newPin = ref('')
const confirmPin = ref('')
const deviceLabel = ref('')
const pinError = ref('')

const feedUrl = computed(() => {
  if (!authStore.user || typeof window === 'undefined') return ''
  return `${window.location.origin}/calendar/${authStore.user.calendar_feed_token}.ics`
})

onMounted(async () => {
  pushSupported.value = push.isSupported()
  if (pushSupported.value) {
    subscribed.value = await push.isSubscribed()
  }
})

notifications.value = await $fetch<NotificationItem[]>('/api/notifications')
deviceTrust.value = await $fetch<DeviceTrustStatus>('/api/auth/device-trust/status')

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

async function onCopyFeedUrl() {
  try {
    await navigator.clipboard.writeText(feedUrl.value)
    copied.value = true
    setTimeout(() => (copied.value = false), 2000)
  } catch {
    // Clipboard API can be unavailable (e.g. insecure context) — the input is still
    // select-on-focus, so the user can copy manually either way.
  }
}

async function onRegenerateFeed() {
  await authStore.regenerateCalendarFeedToken()
}

async function onSaveBirthday() {
  birthdayError.value = ''
  try {
    await authStore.setBirthday(birthdayDraft.value)
  } catch {
    birthdayError.value = 'Could not save that date — try again.'
  }
}

async function onStartTotp() {
  totpError.value = ''
  const res = await $fetch<{ secret: string; qr_data_uri: string }>('/api/auth/2fa/enroll/start', {
    method: 'POST',
  })
  totpSecret.value = res.secret
  totpQrDataUri.value = res.qr_data_uri
  totpCode.value = ''
  totpStep.value = 'enrolling'
}

function onCancelTotp() {
  totpStep.value = 'idle'
  totpCode.value = ''
}

async function onConfirmTotp() {
  totpError.value = ''
  try {
    const res = await $fetch<{ recovery_codes: string[] }>('/api/auth/2fa/enroll/confirm', {
      method: 'POST',
      body: { code: totpCode.value },
    })
    recoveryCodes.value = res.recovery_codes
    totpStep.value = 'recovery-codes'
    if (authStore.user) authStore.user.is_2fa_enabled = true
  } catch {
    totpError.value = 'Invalid code — check your authenticator app and try again.'
  }
}

async function onDisableTotp() {
  disable2faError.value = ''
  try {
    await $fetch('/api/auth/2fa/disable', { method: 'POST', body: { password: disable2faPassword.value } })
    if (authStore.user) authStore.user.is_2fa_enabled = false
    show2faDisableForm.value = false
    disable2faPassword.value = ''
  } catch {
    disable2faError.value = 'Incorrect password.'
  }
}

async function onSetupPin() {
  pinError.value = ''
  if (newPin.value.length < 4) {
    pinError.value = 'PIN must be at least 4 characters.'
    return
  }
  if (newPin.value !== confirmPin.value) {
    pinError.value = 'PINs do not match.'
    return
  }
  try {
    await $fetch('/api/auth/device-trust/enroll', {
      method: 'POST',
      body: { pin: newPin.value, device_label: deviceLabel.value || null },
    })
    deviceTrust.value = { trusted: true, device_label: deviceLabel.value || null }
    newPin.value = ''
    confirmPin.value = ''
    deviceLabel.value = ''
  } catch {
    pinError.value = 'Could not set up the PIN. Try again.'
  }
}

async function onForgetDevice() {
  await $fetch('/api/auth/device-trust/revoke', { method: 'POST' })
  deviceTrust.value = { trusted: false }
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

.card h3 {
  margin-top: 0;
}

.card label {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  font-size: 0.85rem;
  margin-bottom: 0.6rem;
}

.card input {
  padding: 0.5rem;
  border-radius: 0.4rem;
  border: 1px solid var(--border);
  background: var(--bg);
  color: var(--fg);
  font-size: 0.95rem;
}

.card > button {
  padding: 0.5rem 0.9rem;
  border-radius: 0.4rem;
  border: 1px solid var(--border);
  background: var(--bg);
  color: var(--fg);
  font-size: 0.9rem;
}

.status-ok {
  color: #0f766e;
  font-weight: 600;
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

.feed-row {
  display: flex;
  gap: 0.5rem;
  margin: 0.75rem 0;
}

.feed-row input {
  flex: 1;
  min-width: 0;
  padding: 0.5rem;
  border-radius: 0.4rem;
  border: 1px solid var(--border);
  background: var(--bg);
  color: var(--fg);
  font-size: 0.8rem;
}

.feed-row button {
  padding: 0.5rem 0.8rem;
  border-radius: 0.4rem;
  border: 1px solid var(--border);
  background: var(--bg);
  color: var(--fg);
  font-size: 0.85rem;
  white-space: nowrap;
}

.link-btn {
  background: none;
  border: none;
  color: var(--link);
  padding: 0;
  font-size: 0.8rem;
  display: block;
  margin: 0.5rem 0;
}

.inline-form {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 0.5rem;
}

.inline-form input {
  flex: 1;
  padding: 0.5rem;
  border-radius: 0.4rem;
  border: 1px solid var(--border);
  background: var(--bg);
  color: var(--fg);
}

.inline-form button {
  padding: 0.5rem 0.8rem;
  border-radius: 0.4rem;
  border: 1px solid var(--border);
  background: var(--bg);
  color: var(--fg);
  white-space: nowrap;
}

.qr-image {
  width: 180px;
  height: 180px;
  border: 1px solid var(--border);
  border-radius: 0.5rem;
  padding: 0.5rem;
  background: white;
}

.small {
  font-size: 0.8rem;
}

.btn-row {
  display: flex;
  gap: 0.5rem;
}

.btn-row button {
  padding: 0.5rem 0.9rem;
  border-radius: 0.4rem;
  border: 1px solid var(--border);
  background: var(--bg);
  color: var(--fg);
}

.recovery-codes ul {
  list-style: none;
  padding: 0;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.4rem;
  margin: 0.75rem 0;
}

.recovery-codes code {
  display: block;
  background: var(--border);
  padding: 0.3rem 0.5rem;
  border-radius: 0.3rem;
  font-size: 0.85rem;
  text-align: center;
}

.recovery-codes > button {
  padding: 0.5rem 0.9rem;
  border-radius: 0.4rem;
  border: none;
  background: var(--accent);
  color: white;
}

.admin-link {
  display: block;
  color: var(--link);
  text-decoration: none;
  margin-top: 1rem;
  font-size: 0.9rem;
}
</style>
