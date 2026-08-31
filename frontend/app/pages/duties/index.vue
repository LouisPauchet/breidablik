<template>
  <div>
    <header class="page-header">
      <h1>Duties</h1>
      <NuxtLink to="/duties/new" class="btn-primary">+ New</NuxtLink>
    </header>

    <p v-if="!duties.duties.length" class="muted">No duties yet. Create the first one.</p>

    <ul class="duty-list">
      <li v-for="duty in duties.duties" :key="duty.id">
        <NuxtLink :to="`/duties/${duty.id}`" class="duty-card">
          <div class="duty-title">{{ duty.title }}</div>
          <div class="duty-meta">
            On duty: <strong>{{ members.nameOf(duty.current_period.assignee_user_id) }}</strong>
            until {{ formatDate(duty.current_period.end_date) }}
          </div>
        </NuxtLink>
      </li>
    </ul>
  </div>
</template>

<script setup lang="ts">
const duties = useDutiesStore()
const members = useMembersStore()

await Promise.all([members.ensureLoaded(), duties.fetchDuties()])

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}
</script>

<style scoped>
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
}

.btn-primary {
  background: var(--accent);
  color: white;
  padding: 0.5rem 0.9rem;
  border-radius: 0.5rem;
  text-decoration: none;
  font-size: 0.9rem;
}

.muted {
  color: var(--muted);
}

.duty-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
}

.duty-card {
  display: block;
  border: 1px solid var(--border);
  border-radius: 0.75rem;
  padding: 0.9rem;
  text-decoration: none;
  color: var(--fg);
}

.duty-title {
  font-weight: 600;
  margin-bottom: 0.25rem;
}

.duty-meta {
  font-size: 0.85rem;
  color: var(--muted);
}
</style>
