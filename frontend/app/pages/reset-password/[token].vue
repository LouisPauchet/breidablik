<template>
  <div class="reset-page">
    <h1>Breidablik</h1>

    <div v-if="loading" class="card">
      <p class="muted">Checking your reset link…</p>
    </div>

    <div v-else-if="invalidReason" class="card">
      <p class="error">{{ invalidReason }}</p>
      <p class="muted small">Ask an admin to send you a new link.</p>
    </div>

    <form v-else-if="step === 'twofa'" class="card" @submit.prevent="submitTwoFactor">
      <p>Password updated. Enter the 6-digit code from your authenticator app (or a recovery code) to sign in.</p>
      <label>
        Code
        <input v-model="code" required autocomplete="one-time-code" />
      </label>
      <p v-if="error" class="error">{{ error }}</p>
      <button type="submit" :disabled="submitting">Verify</button>
    </form>

    <form v-else class="card" @submit.prevent="submit">
      <p>Hi <strong>{{ reset?.display_name }}</strong>, choose a new password for {{ reset?.email }}.</p>
      <label>
        New password
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
const reset = ref<{ display_name: string; email: string } | null>(null)
const step = ref<'password' | 'twofa'>('password')
const password = ref('')
const confirmPassword = ref('')
const code = ref('')
const submitting = ref(false)
const error = ref('')

onMounted(async () => {
  try {
    reset.value = await authStore.fetchPasswordReset(token)
  } catch (err: unknown) {
    const status = (err as { statusCode?: number; response?: { status?: number } })?.statusCode
      ?? (err as { response?: { status?: number } })?.response?.status
    invalidReason.value =
      status === 410 ? 'This reset link has expired.' : 'This reset link is invalid or was already used.'
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
    const result = await authStore.redeemPasswordReset(token, password.value)
    if (result.requires_2fa) {
      step.value = 'twofa'
      return
    }
    await router.push('/')
  } catch {
    error.value = 'Could not set your password — try again.'
  } finally {
    submitting.value = false
  }
}

async function submitTwoFactor() {
  error.value = ''
  submitting.value = true
  try {
    await authStore.verify2fa(code.value)
    await router.push('/')
  } catch {
    error.value = 'That code was not accepted.'
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.reset-page {
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
