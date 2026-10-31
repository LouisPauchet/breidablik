<template>
  <div v-if="enabled" class="card">
    <h3>Passkeys</h3>
    <p class="muted small">
      Sign in with your fingerprint, face or device PIN instead of a password. A passkey already
      counts as two factors, so it skips the authenticator code.
    </p>

    <p v-if="!supported" class="muted small">This browser can't create passkeys.</p>

    <ul v-if="passkeys.length" class="passkey-list">
      <li v-for="p in passkeys" :key="p.id" class="passkey-row">
        <div>
          <strong>{{ p.label || 'Passkey' }}</strong>
          <div class="muted small">
            Added {{ formatDate(p.created_at) }}<template v-if="p.last_used_at"> · used {{ formatDate(p.last_used_at) }}</template>
          </div>
        </div>
        <button type="button" :disabled="busy" @click="onRemove(p)">Remove</button>
      </li>
    </ul>
    <p v-else class="muted small">No passkeys yet.</p>

    <template v-if="supported">
      <label>
        Name this passkey
        <input v-model="label" maxlength="100" placeholder="e.g. Laptop" />
      </label>
      <button type="button" class="add-btn" :disabled="busy" @click="onAdd">Add a passkey</button>
    </template>

    <p v-if="notice" :class="noticeIsError ? 'error' : 'status-ok'">{{ notice }}</p>
  </div>
</template>

<script setup lang="ts">
interface PasskeyItem {
  id: string
  label: string | null
  created_at: string | null
  last_used_at: string | null
}

const ERRORS: Record<string, string> = {
  LAST_SIGNIN_METHOD: "That's your only way to sign in — add another passkey or turn password login back on first.",
  PASSKEY_REGISTRATION_FAILED: 'That passkey could not be verified — try again.',
}

const enabled = ref(false)
const passkeys = ref<PasskeyItem[]>([])
const label = ref('')
const busy = ref(false)
const notice = ref('')
const noticeIsError = ref(false)

const supported = computed(
  () =>
    typeof window !== 'undefined' &&
    'PublicKeyCredential' in window &&
    typeof PublicKeyCredential.parseCreationOptionsFromJSON === 'function',
)

function setNotice(message: string, isError: boolean) {
  notice.value = message
  noticeIsError.value = isError
}

function errorMessage(err: unknown, fallback: string) {
  const detail = (err as { data?: { detail?: string } })?.data?.detail ?? ''
  return ERRORS[detail] ?? fallback
}

function formatDate(iso: string | null) {
  return iso ? new Date(iso).toLocaleDateString(undefined, { dateStyle: 'medium' }) : ''
}

async function refresh() {
  passkeys.value = await $fetch<PasskeyItem[]>('/api/auth/passkeys')
}

async function onAdd() {
  busy.value = true
  setNotice('', false)
  try {
    const options = await $fetch<PublicKeyCredentialCreationOptionsJSON>('/api/auth/passkeys/register/options', {
      method: 'POST',
    })
    const credential = (await navigator.credentials.create({
      publicKey: PublicKeyCredential.parseCreationOptionsFromJSON(options),
    })) as PublicKeyCredential | null
    if (!credential) return
    await $fetch('/api/auth/passkeys/register/verify', {
      method: 'POST',
      body: { credential: credential.toJSON(), label: label.value.trim() || null },
    })
    label.value = ''
    await refresh()
    setNotice('Passkey added.', false)
  } catch (err) {
    // The member dismissing the browser prompt isn't an error worth shouting about.
    if ((err as { name?: string })?.name === 'NotAllowedError') {
      setNotice('Cancelled.', false)
    } else {
      setNotice(errorMessage(err, 'Could not add a passkey — try again.'), true)
    }
  } finally {
    busy.value = false
  }
}

async function onRemove(p: PasskeyItem) {
  if (!window.confirm(`Remove "${p.label || 'this passkey'}"?`)) return
  busy.value = true
  setNotice('', false)
  try {
    await $fetch(`/api/auth/passkeys/${p.id}`, { method: 'DELETE' })
    await refresh()
  } catch (err) {
    setNotice(errorMessage(err, 'Could not remove that passkey.'), true)
  } finally {
    busy.value = false
  }
}

try {
  const config = await $fetch<{ enabled: boolean }>('/api/auth/passkeys/config')
  enabled.value = config.enabled
  if (config.enabled) await refresh()
} catch {
  // Optional feature: if this can't load, the section just stays hidden.
}
</script>

<style scoped>
.card {
  border: 1px solid var(--border);
  border-radius: 0.75rem;
  padding: 1rem;
  margin-bottom: 1.5rem;
}

.card h3 {
  margin-top: 0;
}

.muted {
  color: var(--muted);
}

.small {
  font-size: 0.8rem;
}

.error {
  color: #dc2626;
  font-size: 0.85rem;
}

.status-ok {
  color: #16a34a;
  font-size: 0.85rem;
}

.passkey-list {
  list-style: none;
  padding: 0;
  margin: 0 0 0.75rem;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.passkey-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.5rem;
}

label {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  font-size: 0.85rem;
  margin-bottom: 0.6rem;
}

input {
  padding: 0.5rem;
  border-radius: 0.4rem;
  border: 1px solid var(--border);
  background: var(--bg);
  color: var(--fg);
  font-size: 0.95rem;
}

button {
  padding: 0.45rem 0.9rem;
  border-radius: 0.4rem;
  border: 1px solid var(--border);
  background: var(--bg);
  color: var(--fg);
  font-size: 0.9rem;
}
</style>
