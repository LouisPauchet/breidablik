<template>
  <div>
    <PageHeader :title="`Hi ${authStore.user?.display_name}`" />

    <h2>Your duties</h2>
    <p v-if="!myDuties.length" class="muted">Nothing on your plate right now.</p>
    <ul class="widget-list highlight">
      <li v-for="entry in myDuties" :key="entry.duty_id">
        <NuxtLink :to="`/duties/${entry.duty_id}`">
          <strong>{{ entry.duty_title }}</strong>
        </NuxtLink>
      </li>
    </ul>

    <h2>Household duties</h2>
    <p v-if="!duties.onDutyToday.length" class="muted">No active duties yet.</p>
    <ul class="widget-list">
      <li v-for="entry in duties.onDutyToday" :key="entry.duty_id">
        <NuxtLink :to="`/duties/${entry.duty_id}`" class="duty-row">
          <Avatar
            :user-id="entry.assignee_user_id"
            :name="members.nameOf(entry.assignee_user_id)"
            :avatar-updated-at="members.avatarUpdatedAtOf(entry.assignee_user_id)"
            :size="28"
          />
          <span><strong>{{ entry.duty_title }}</strong> — {{ members.nameOf(entry.assignee_user_id) }}</span>
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

const myDuties = computed(() =>
  duties.onDutyToday.filter((entry) => entry.assignee_user_id === authStore.user?.id)
)

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

.widget-list.highlight a {
  background: color-mix(in srgb, var(--accent) 12%, transparent);
  border-color: var(--accent);
}

.widget-list a.duty-row {
  display: flex;
  align-items: center;
  gap: 0.6rem;
}

button {
  padding: 0.6rem 1rem;
  border-radius: 0.5rem;
  border: 1px solid var(--border);
  background: var(--bg);
  color: var(--fg);
}
</style>
