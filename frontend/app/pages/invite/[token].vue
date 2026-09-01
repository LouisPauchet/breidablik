<template>
  <div class="invite-page">
    <h1>Breidablik</h1>

    <div v-if="loading" class="card">
      <p class="muted">Checking your invite…</p>
    </div>

    <div v-else-if="invalidReason" class="card">
      <p class="error">{{ invalidReason }}</p>
      <p class="muted small">Ask whoever invited you to send a new link.</p>
    </div>

    <form v-else class="card" @submit.prevent="submit">
      <p>Welcome, <strong>{{ invite?.display_name }}</strong>! Set a password to finish setting up your account ({{ invite?.email }}).</p>
      <label>
        Password
        <input v-model="password" type="password" required minlength="8" autocomplete="new-password" />
      </label>
      <label>
        Confirm password
        <input v-model="confirmPassword" type="password" required minlength="8" autocomplete="new-password" />
      </label>
      <p v-if="error" class="error">{{ error }}</p>
      <button type="submit" :disabled="submitting">Set password &amp; continue</button>
    </form>
  </div>
</template>

<script setup lang="ts">
definePageMeta({ layout: false })

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()

const token = route.params.token as string

const loading = ref(true)
const invalidReason = ref('')
const invite = ref<{ display_name: string; email: string } | null>(null)
const password = ref('')
const confirmPassword = ref('')
const submitting = ref(false)
const error = ref('')

onMounted(async () => {
  try {
    invite.value = await authStore.fetchInvite(token)
  } catch (err: unknown) {
    const status = (err as { statusCode?: number; response?: { status?: number } })?.statusCode
      ?? (err as { response?: { status?: number } })?.response?.status
    invalidReason.value =
      status === 410 ? 'This invite link has expired.' : 'This invite link is invalid.'
  } finally {
    loading.value = false
  }
})

async function submit() {
  error.value = ''
  if (password.value !== confirmPassword.value) {
    error.value = 'Passwords do not match.'
    return
  }
  submitting.value = true
  try {
    await authStore.acceptInvite(token, password.value)
    await router.push('/')
  } catch {
    error.value = 'Could not set your password — try again.'
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.invite-page {
  max-width: 360px;
  margin: 3rem auto;
  padding: 0 1rem;
}

.card {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  border: 1px solid var(--border);
  border-radius: 0.75rem;
  padding: 1.25rem;
  margin-bottom: 1rem;
}

label {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  font-size: 0.9rem;
}

input {
  padding: 0.6rem;
  border-radius: 0.5rem;
  border: 1px solid var(--border);
  background: var(--bg);
  color: var(--fg);
  font-size: 1rem;
}

button {
  padding: 0.65rem;
  border-radius: 0.5rem;
  border: none;
  background: var(--accent);
  color: white;
  font-size: 1rem;
}

.muted {
  color: var(--muted);
}

.small {
  font-size: 0.85rem;
}

.error {
  color: #dc2626;
  font-size: 0.85rem;
}
</style>
