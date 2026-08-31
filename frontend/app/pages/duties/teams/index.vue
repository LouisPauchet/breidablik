<template>
  <div>
    <header class="page-header">
      <h1>Duty teams</h1>
      <NuxtLink to="/duties/teams/new" class="btn-primary">+ New</NuxtLink>
    </header>
    <NuxtLink to="/duties" class="back-link">&larr; Duties</NuxtLink>

    <p v-if="!teams.teams.length" class="muted">No teams yet.</p>
    <ul class="team-list">
      <li v-for="team in teams.teams" :key="team.id">
        <NuxtLink :to="`/duties/teams/${team.id}`" class="team-card">
          <div class="team-title">{{ team.name }}</div>
          <div class="team-meta">
            {{ team.members.length }} member(s) &middot; {{ team.duties.filter((d) => d.is_active).length }} duty(ies)
            &middot; rotates every {{ team.rotation_interval_days }} days
          </div>
        </NuxtLink>
      </li>
    </ul>
  </div>
</template>

<script setup lang="ts">
const teams = useDutyTeamsStore()
await teams.fetchTeams()
</script>

<style scoped>
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.5rem;
}

.back-link {
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

.team-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
}

.team-card {
  display: block;
  border: 1px solid var(--border);
  border-radius: 0.75rem;
  padding: 0.9rem;
  text-decoration: none;
  color: var(--fg);
}

.team-title {
  font-weight: 600;
  margin-bottom: 0.25rem;
}

.team-meta {
  font-size: 0.85rem;
  color: var(--muted);
}
</style>
