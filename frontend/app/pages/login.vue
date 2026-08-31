<template>
  <div class="login-page">
    <h1>Breidablik</h1>

    <form v-if="step === 'credentials'" class="card" @submit.prevent="submitCredentials">
      <label>
        Email
        <input v-model="email" type="email" required autocomplete="username" />
      </label>
      <label>
        Password
        <input v-model="password" type="password" required autocomplete="current-password" />
      </label>
      <p v-if="error" class="error">{{ error }}</p>
      <button type="submit" :disabled="loading">Log in</button>

      <button type="button" class="link" @click="showPin = !showPin">
        {{ showPin ? 'Hide PIN login' : 'Use a PIN on this device instead' }}
      </button>
    </form>

    <form v-if="step === 'credentials' && showPin" class="card" @submit.prevent="submitPin">
      <label>
        PIN
        <input v-model="pin" type="password" inputmode="numeric" required autocomplete="off" />
      </label>
      <p v-if="pinError" class="error">{{ pinError }}</p>
      <button type="submit" :disabled="loading">Unlock</button>
    </form>

    <form v-if="step === 'twofa'" class="card" @submit.prevent="submitTwoFactor">
      <p>Enter the 6-digit code from your authenticator app (or a recovery code).</p>
      <label>
        Code
        <input v-model="code" required autocomplete="one-time-code" />
      </label>
      <p v-if="error" class="error">{{ error }}</p>
      <button type="submit" :disabled="loading">Verify</button>
    </form>
  </div>
</template>

<script setup lang="ts">
definePageMeta({ layout: false })

const authStore = useAuthStore()
const router = useRouter()

const step = ref<'credentials' | 'twofa'>('credentials')
const email = ref('')
const password = ref('')
const code = ref('')
const pin = ref('')
const showPin = ref(false)
const loading = ref(false)
const error = ref('')
const pinError = ref('')

async function submitCredentials() {
  error.value = ''
  loading.value = true
  try {
    const result = await authStore.login(email.value, password.value)
    if (result.requires_2fa) {
      step.value = 'twofa'
    } else if (result.user) {
      authStore.user = result.user
      await router.push('/')
    }
  } catch {
    error.value = 'Incorrect email or password.'
  } finally {
    loading.value = false
  }
}

async function submitTwoFactor() {
  error.value = ''
  loading.value = true
  try {
    await authStore.verify2fa(code.value)
    await router.push('/')
  } catch {
    error.value = 'Invalid or expired code.'
  } finally {
    loading.value = false
  }
}

async function submitPin() {
  pinError.value = ''
  loading.value = true
  try {
    await authStore.loginPin(pin.value)
    await router.push('/')
  } catch {
    pinError.value = 'This device is not trusted yet, or the PIN is wrong — log in with your password.'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
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

button.link {
  background: none;
  color: var(--link);
  padding: 0.25rem;
}

.error {
  color: #dc2626;
  font-size: 0.85rem;
}
</style>
