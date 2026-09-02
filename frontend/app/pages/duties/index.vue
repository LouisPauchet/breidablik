<template>
  <div>
    <PageHeader title="Duties">
      <NuxtLink to="/duties/new" class="btn-primary">+ New</NuxtLink>
    </PageHeader>
    <NuxtLink to="/duties/teams" class="teams-link">Manage duty teams &rarr;</NuxtLink>

    <p v-if="!duties.duties.length" class="muted">No duties yet. Create the first one.</p>

    <ul class="duty-list">
      <li v-for="duty in duties.duties" :key="duty.id" class="duty-row">
        <NuxtLink :to="`/members/${duty.current_period.assignee_user_id}`" class="avatar-link">
          <Avatar
            :user-id="duty.current_period.assignee_user_id"
            :name="members.nameOf(duty.current_period.assignee_user_id)"
            :avatar-updated-at="members.avatarUpdatedAtOf(duty.current_period.assignee_user_id)"
            :size="32"
          />
        </NuxtLink>
        <NuxtLink :to="`/duties/${duty.id}`" class="duty-card">
          <div class="duty-title">
            {{ duty.title }}
            <span v-if="duty.team_id" class="badge">{{ teams.nameOf(duty.team_id) }}</span>
          </div>
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
const teams = useDutyTeamsStore()

await Promise.all([members.ensureLoaded(), duties.fetchDuties(), teams.fetchTeams()])

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}
</script>

<style scoped>
.teams-link {
  display: inline-block;
  color: var(--link);
  text-decoration: none;
  font-size: 0.85rem;
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

.duty-row {
  display: flex;
  align-items: center;
  gap: 0.6rem;
}

.avatar-link {
  display: inline-flex;
  flex-shrink: 0;
}

.duty-card {
  display: block;
  flex: 1;
  min-width: 0;
  border: 1px solid var(--border);
  border-radius: 0.75rem;
  padding: 0.9rem;
  text-decoration: none;
  color: var(--fg);
}

.duty-title {
  font-weight: 600;
  margin-bottom: 0.25rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.badge {
  font-size: 0.7rem;
  font-weight: 400;
  background: #0f766e;
  color: white;
  border-radius: 999px;
  padding: 0.1rem 0.5rem;
}

.duty-meta {
  font-size: 0.85rem;
  color: var(--muted);
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.35rem;
}
</style>
