<template>
  <div>
    <h1>Hi {{ authStore.user?.display_name }}</h1>

    <h2>On duty today</h2>
    <p v-if="!duties.onDutyToday.length" class="muted">No active duties yet.</p>
    <ul class="widget-list">
      <li v-for="entry in duties.onDutyToday" :key="entry.duty_id">
        <NuxtLink :to="`/duties/${entry.duty_id}`">
          <strong>{{ entry.duty_title }}</strong> — {{ members.nameOf(entry.assignee_user_id) }}
        </NuxtLink>
      </li>
    </ul>

    <button @click="handleLogout">Log out</button>
  </div>
</template>

<script setup lang="ts">
const authStore = useAuthStore()
const duties = useDutiesStore()
const members = useMembersStore()
const router = useRouter()

await Promise.all([members.ensureLoaded(), duties.fetchOnDutyToday()])

async function handleLogout() {
  await authStore.logout()
  await router.push('/login')
}
</script>

<style scoped>
.muted {
  color: var(--muted);
}

.widget-list {
  list-style: none;
  padding: 0;
  margin: 0 0 1.5rem;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.widget-list a {
  display: block;
  border: 1px solid var(--border);
  border-radius: 0.6rem;
  padding: 0.7rem;
  color: var(--fg);
  text-decoration: none;
}

button {
  padding: 0.6rem 1rem;
  border-radius: 0.5rem;
  border: 1px solid var(--border);
  background: var(--bg);
  color: var(--fg);
}
</style>
