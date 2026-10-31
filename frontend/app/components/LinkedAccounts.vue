<template>
  <div v-if="providers.length || linked.length" class="card">
    <h3>Linked accounts</h3>
    <p class="muted small">
      Link a Google or GitHub account to sign in with it. You must already have an account here —
      linking never creates one.
    </p>

    <p v-if="notice" :class="noticeIsError ? 'error' : 'status-ok'">{{ notice }}</p>

    <ul class="account-list">
      <li v-for="name in providerNames" :key="name" class="account-row">
        <div>
          <strong>{{ LABELS[name] ?? name }}</strong>
          <div v-if="linkedBy(name)" class="muted small">{{ linkedBy(name)?.account_email ?? 'Linked' }}</div>
        </div>
        <button v-if="linkedBy(name)" type="button" :disabled="busy" @click="onUnlink(name)">Unlink</button>
        <button v-else type="button" :disabled="busy" @click="onLink(name)">Link</button>
      </li>
    </ul>
  </div>
</template>

<script setup lang="ts">
interface LinkedAccount {
  provider: string
  account_email: string | null
}

const LABELS: Record<string, string> = { google: 'Google', github: 'GitHub' }

const ERRORS: Record<string, string> = {
  LAST_SIGNIN_METHOD: "That's your only way to sign in — add another before unlinking it.",
  ALREADY_LINKED: 'That provider is already linked.',
}

const route = useRoute()

const providers = ref<string[]>([])
const linked = ref<LinkedAccount[]>([])
const busy = ref(false)
const notice = ref('')
const noticeIsError = ref(false)

// Show a provider if it's enabled, or if it's linked but has since been switched off, so the
// member can still unlink it.
const providerNames = computed(() =>
  [...new Set([...providers.value, ...linked.value.map((a) => a.provider)])].sort(),
)

function linkedBy(name: string) {
  return linked.value.find((a) => a.provider === name)
}

function setNotice(message: string, isError: boolean) {
  notice.value = message
  noticeIsError.value = isError
}

async function refresh() {
  const [enabled, accounts] = await Promise.all([
    $fetch<string[]>('/api/auth/oauth/providers'),
    $fetch<LinkedAccount[]>('/api/auth/oauth/accounts'),
  ])
  providers.value = enabled
  linked.value = accounts
}

async function onLink(name: string) {
  busy.value = true
  setNotice('', false)
  try {
    const res = await $fetch<{ authorization_url: string }>(`/api/auth/oauth/${name}/link`, { method: 'POST' })
    window.location.href = res.authorization_url
  } catch (err) {
    const detail = (err as { data?: { detail?: string } })?.data?.detail ?? ''
    setNotice(ERRORS[detail] ?? 'Could not start linking — try again.', true)
    busy.value = false
  }
}

async function onUnlink(name: string) {
  busy.value = true
  setNotice('', false)
  try {
    await $fetch(`/api/auth/oauth/${name}`, { method: 'DELETE' })
    await refresh()
  } catch (err) {
    const detail = (err as { data?: { detail?: string } })?.data?.detail ?? ''
    setNotice(ERRORS[detail] ?? 'Could not unlink — try again.', true)
  } finally {
    busy.value = false
  }
}

try {
  await refresh()
} catch {
  // Optional feature: if this can't load, the section just stays hidden.
}

// The provider redirects back to /profile?oauth=linked|error.
if (route.query.oauth === 'linked') setNotice('Account linked.', false)
else if (route.query.oauth === 'error') setNotice('Could not link that account — try again.', true)
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

.account-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.account-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.5rem;
}

.account-row button {
  padding: 0.4rem 0.8rem;
  border-radius: 0.4rem;
  border: 1px solid var(--border);
  background: var(--bg);
  color: var(--fg);
  font-size: 0.85rem;
}
</style>
