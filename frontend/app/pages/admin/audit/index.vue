<template>
  <div v-if="authStore.user?.is_superuser">
    <PageHeader title="Audit log" back="/admin/members" />

    <p v-if="loadError" class="error">{{ loadError }}</p>
    <p v-else-if="!entries.length && !loading" class="muted">Nothing has been recorded yet.</p>

    <ul class="entry-list">
      <li v-for="entry in entries" :key="entry.id" class="entry">
        <div class="entry-main">
          <strong>{{ entry.actor_name ?? 'A removed account' }}</strong>
          {{ describe(entry) }}
          <strong v-if="entry.target_name">{{ entry.target_name }}</strong>
        </div>
        <div class="muted small">{{ formatWhen(entry.created_at) }}</div>
      </li>
    </ul>

    <button v-if="hasMore" type="button" class="more-btn" :disabled="loading" @click="loadMore">
      Load more
    </button>
  </div>
</template>

<script setup lang="ts">
interface AuditEntry {
  id: string
  actor_name: string | null
  target_name: string | null
  action: string
  detail: Record<string, unknown> | null
  created_at: string
}

const PAGE_SIZE = 50

const authStore = useAuthStore()

if (!authStore.user?.is_superuser) {
  await navigateTo('/')
}

const entries = ref<AuditEntry[]>([])
const hasMore = ref(false)
const loading = ref(false)
const loadError = ref('')

function describe(entry: AuditEntry) {
  switch (entry.action) {
    case 'user.deactivated':
      return 'deactivated'
    case 'user.reactivated':
      return 'reactivated'
    case 'user.sessions_revoked':
      return 'signed out everywhere'
    case 'user.password_reset_issued':
      return entry.detail?.reset_2fa
        ? 'generated a password and 2FA reset link for'
        : 'generated a password reset link for'
    case 'user.role_changed':
      return entry.detail?.is_superuser ? 'made an admin' : 'removed the admin role from'
    default:
      return entry.action
  }
}

function formatWhen(iso: string) {
  return new Date(iso).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })
}

async function loadMore() {
  loading.value = true
  loadError.value = ''
  try {
    const page = await $fetch<AuditEntry[]>('/api/admin/audit-log', {
      query: { limit: PAGE_SIZE, offset: entries.value.length },
    })
    entries.value.push(...page)
    hasMore.value = page.length === PAGE_SIZE
  } catch {
    loadError.value = 'Could not load the audit log.'
  } finally {
    loading.value = false
  }
}

if (authStore.user?.is_superuser) {
  await loadMore()
}
</script>

<style scoped>
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

.entry-list {
  list-style: none;
  padding: 0;
  margin: 1rem 0;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.entry {
  border: 1px solid var(--border);
  border-radius: 0.6rem;
  padding: 0.7rem;
}

.more-btn {
  width: 100%;
  padding: 0.65rem;
  border-radius: 0.5rem;
  border: 1px solid var(--border);
  background: var(--bg);
  color: var(--fg);
  font-size: 1rem;
}
</style>
