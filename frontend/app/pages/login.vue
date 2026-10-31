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

    <div v-if="step === 'credentials' && passkeysAvailable" class="card">
      <button type="button" :disabled="loading" @click="submitPasskey">Sign in with a passkey</button>
      <p v-if="passkeyError" class="error">{{ passkeyError }}</p>
    </div>

    <div v-if="step === 'credentials' && (providers.length || oauthNotice)" class="card">
      <p v-if="oauthNotice" class="error">{{ oauthNotice }}</p>
      <!-- Plain links, not router links: the server redirects on to the provider. -->
      <a
        v-for="name in providers"
        :key="name"
        class="provider-btn"
        :href="`/api/auth/oauth/${name}/login`"
      >
        Continue with {{ PROVIDER_LABELS[name] ?? name }}
      </a>
    </div>

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
const route = useRoute()

const PROVIDER_LABELS: Record<string, string> = { google: 'Google', github: 'GitHub' }

const OAUTH_NOTICES: Record<string, string> = {
  unlinked: 'That account is not linked to a member here. Sign in another way and link it from your profile.',
  error: 'Could not sign in with that account — try again.',
}

// The server redirects back here as /login?oauth=2fa once the provider sign-in succeeded
// but the member still owes their authenticator code (it has set the pending-2FA cookie).
const step = ref<'credentials' | 'twofa'>(route.query.oauth === '2fa' ? 'twofa' : 'credentials')
const providers = ref<string[]>([])
const oauthNotice = OAUTH_NOTICES[String(route.query.oauth ?? '')] ?? ''

const passkeysAvailable = ref(false)
const passkeyError = ref('')

onMounted(async () => {
  try {
    providers.value = await $fetch<string[]>('/api/auth/oauth/providers')
  } catch {
    // Optional feature: password login still works without the buttons.
  }
  try {
    const config = await $fetch<{ enabled: boolean }>('/api/auth/passkeys/config')
    passkeysAvailable.value =
      config.enabled && 'PublicKeyCredential' in window && typeof PublicKeyCredential.parseRequestOptionsFromJSON === 'function'
  } catch {
    // Same: just no passkey button.
  }
})

async function submitPasskey() {
  passkeyError.value = ''
  loading.value = true
  try {
    await authStore.loginPasskey()
    if (authStore.user) await router.push('/')
  } catch (err) {
    // Dismissing the browser's passkey prompt is not worth an error message.
    if ((err as { name?: string })?.name !== 'NotAllowedError') {
      passkeyError.value = 'Could not sign in with a passkey — try another way.'
    }
  } finally {
    loading.value = false
  }
}
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

.provider-btn {
  display: block;
  text-align: center;
  padding: 0.65rem;
  border-radius: 0.5rem;
  border: 1px solid var(--border);
  background: var(--bg);
  color: var(--fg);
  font-size: 1rem;
  text-decoration: none;
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
