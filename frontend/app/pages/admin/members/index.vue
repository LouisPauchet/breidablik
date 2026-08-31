<template>
  <div v-if="authStore.user?.is_superuser">
    <PageHeader title="Members" back="/profile" />

    <ul class="member-list">
      <li v-for="member in members" :key="member.id" class="member-row">
        <div>
          <div class="member-name">
            {{ member.display_name }}
            <span v-if="member.is_superuser" class="badge">admin</span>
            <span v-if="!member.is_active" class="badge inactive">inactive</span>
          </div>
          <div class="muted">{{ member.email }}</div>
          <div v-if="member.birthday" class="muted">🎂 {{ formatBirthday(member.birthday) }}</div>
        </div>
        <div class="member-actions">
          <button type="button" @click="onToggleActive(member)">
            {{ member.is_active ? 'Deactivate' : 'Activate' }}
          </button>
          <button type="button" @click="onToggleSuperuser(member)">
            {{ member.is_superuser ? 'Remove admin' : 'Make admin' }}
          </button>
        </div>
      </li>
    </ul>

    <h2>Add a member</h2>
    <form class="card" @submit.prevent="submit">
      <label>
        Display name
        <input v-model="displayName" required />
      </label>
      <label>
        Email
        <input v-model="email" type="email" required />
      </label>
      <label>
        Initial password
        <input v-model="password" type="text" required minlength="8" />
      </label>
      <label class="checkbox-row">
        <input v-model="isSuperuser" type="checkbox" />
        Admin (can manage members)
      </label>
      <p v-if="error" class="error">{{ error }}</p>
      <button type="submit" class="submit-btn" :disabled="loading">Create member</button>
    </form>
  </div>
</template>

<script setup lang="ts">
interface Member {
  id: string
  email: string
  display_name: string
  is_active: boolean
  is_superuser: boolean
  is_verified: boolean
  is_2fa_enabled: boolean
  birthday: string | null
}

const authStore = useAuthStore()

if (!authStore.user?.is_superuser) {
  await navigateTo('/')
}

function formatBirthday(iso: string) {
  return new Date(iso).toLocaleDateString(undefined, { month: 'long', day: 'numeric' })
}

const members = ref<Member[]>([])
members.value = await $fetch<Member[]>('/api/admin/users')

const displayName = ref('')
const email = ref('')
const password = ref('')
const isSuperuser = ref(false)
const loading = ref(false)
const error = ref('')

async function submit() {
  error.value = ''
  loading.value = true
  try {
    const created = await $fetch<Member>('/api/admin/users', {
      method: 'POST',
      body: {
        display_name: displayName.value,
        email: email.value,
        password: password.value,
        is_superuser: isSuperuser.value,
      },
    })
    members.value.push(created)
    displayName.value = ''
    email.value = ''
    password.value = ''
    isSuperuser.value = false
  } catch {
    error.value = 'Could not create that member — the email may already be in use.'
  } finally {
    loading.value = false
  }
}

async function onToggleActive(member: Member) {
  const updated = await $fetch<Member>(`/api/users/${member.id}`, {
    method: 'PATCH',
    body: { is_active: !member.is_active },
  })
  Object.assign(member, updated)
}

async function onToggleSuperuser(member: Member) {
  const updated = await $fetch<Member>(`/api/users/${member.id}`, {
    method: 'PATCH',
    body: { is_superuser: !member.is_superuser },
  })
  Object.assign(member, updated)
}
</script>

<style scoped>
.muted {
  color: var(--muted);
}

.member-list {
  list-style: none;
  padding: 0;
  margin: 1rem 0 1.5rem;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.member-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  border: 1px solid var(--border);
  border-radius: 0.6rem;
  padding: 0.7rem;
  gap: 0.5rem;
}

.member-name {
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 0.4rem;
}

.badge {
  font-size: 0.65rem;
  font-weight: 400;
  background: var(--accent);
  color: white;
  border-radius: 999px;
  padding: 0.1rem 0.4rem;
}

.badge.inactive {
  background: #dc2626;
}

.member-actions {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
}

.member-actions button {
  padding: 0.3rem 0.6rem;
  border-radius: 0.4rem;
  border: 1px solid var(--border);
  background: var(--bg);
  color: var(--fg);
  font-size: 0.75rem;
  white-space: nowrap;
}

.card {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  border: 1px solid var(--border);
  border-radius: 0.75rem;
  padding: 1.25rem;
}

label {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  font-size: 0.9rem;
}

.checkbox-row {
  flex-direction: row;
  align-items: center;
  gap: 0.5rem;
}

.checkbox-row input {
  width: auto;
  padding: 0;
}

input {
  padding: 0.6rem;
  border-radius: 0.5rem;
  border: 1px solid var(--border);
  background: var(--bg);
  color: var(--fg);
  font-size: 1rem;
}

.submit-btn {
  padding: 0.65rem;
  border-radius: 0.5rem;
  border: none;
  background: var(--accent);
  color: white;
  font-size: 1rem;
}

.error {
  color: #dc2626;
  font-size: 0.85rem;
}
</style>
