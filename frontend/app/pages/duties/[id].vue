<template>
  <div v-if="duty">
    <PageHeader :title="duty.title" back="/duties" />

    <p v-if="duty.description" class="muted">{{ duty.description }}</p>

    <div class="info-card">
      <div>Needs doing every <strong>{{ duty.task_interval_days }}</strong> day(s)</div>
      <template v-if="duty.team_id">
        <div>
          Part of team: <NuxtLink :to="`/duties/teams/${duty.team_id}`">{{ teams.nameOf(duty.team_id) }}</NuxtLink>
        </div>
      </template>
      <template v-else>
        <div>Responsibility rotates every <strong>{{ duty.rotation_interval_days }}</strong> day(s)</div>
        <div>
          Rotation order:
          <strong>{{ duty.assignees.map((a) => members.nameOf(a.user_id)).join(' -> ') }}</strong>
        </div>
      </template>
      <div>
        Currently on duty: <strong>{{ members.nameOf(duty.current_period.assignee_user_id) }}</strong>
        (until {{ formatDate(duty.current_period.end_date) }})
      </div>
    </div>

    <h2>Upcoming</h2>
    <ul class="occurrence-list">
      <li v-for="occ in duty.occurrences" :key="occ.id" class="occurrence-row">
        <label class="done-toggle">
          <input type="checkbox" :checked="occ.is_done" @change="onToggleDone(occ.id)" />
          <span :class="{ done: occ.is_done }">{{ formatDate(occ.due_date) }}</span>
        </label>
        <select :value="occ.assigned_user_id" @change="onReassign(occ.id, $event)">
          <option v-for="m in members.members" :key="m.id" :value="m.id">{{ m.display_name }}</option>
        </select>
        <span v-if="occ.is_manual_override" class="badge">swapped</span>
        <span v-if="occ.assignee_away" class="badge away" title="Assigned person marked themselves away for this date">
          away — reassign?
        </span>
      </li>
    </ul>

    <div class="danger-zone">
      <button type="button" @click="onArchive">Archive duty</button>
      <button type="button" class="danger" @click="onDelete">Delete duty</button>
    </div>
  </div>
</template>

<script setup lang="ts">
const route = useRoute()
const router = useRouter()
const duties = useDutiesStore()
const members = useMembersStore()
const teams = useDutyTeamsStore()

await Promise.all([members.ensureLoaded(), teams.fetchTeams(), duties.fetchDuty(route.params.id as string)])

const duty = computed(() => duties.current)

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

async function onToggleDone(occurrenceId: string) {
  await duties.toggleOccurrenceDone(route.params.id as string, occurrenceId)
}

async function onReassign(occurrenceId: string, event: Event) {
  const userId = (event.target as HTMLSelectElement).value
  await duties.reassignOccurrence(route.params.id as string, occurrenceId, userId)
}

async function onArchive() {
  await duties.archiveDuty(route.params.id as string)
  await router.push('/duties')
}

async function onDelete() {
  await duties.deleteDuty(route.params.id as string)
  await router.push('/duties')
}
</script>

<style scoped>
.muted {
  color: var(--muted);
}

.info-card {
  border: 1px solid var(--border);
  border-radius: 0.75rem;
  padding: 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  font-size: 0.9rem;
  margin: 1rem 0;
}

.info-card a {
  color: var(--link);
}

.occurrence-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.occurrence-row {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  border: 1px solid var(--border);
  border-radius: 0.5rem;
  padding: 0.6rem;
  font-size: 0.9rem;
}

.done-toggle {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  flex: 1;
}

.done-toggle span.done {
  text-decoration: line-through;
  color: var(--muted);
}

select {
  padding: 0.3rem;
  border-radius: 0.4rem;
  border: 1px solid var(--border);
  background: var(--bg);
  color: var(--fg);
}

.badge {
  font-size: 0.7rem;
  background: var(--accent);
  color: white;
  padding: 0.15rem 0.45rem;
  border-radius: 999px;
  white-space: nowrap;
}

.badge.away {
  background: #d97706;
}

.danger-zone {
  margin-top: 1.5rem;
  display: flex;
  gap: 0.6rem;
}

.danger-zone button {
  padding: 0.55rem 0.9rem;
  border-radius: 0.5rem;
  border: 1px solid var(--border);
  background: var(--bg);
  color: var(--fg);
}

.danger-zone button.danger {
  color: #dc2626;
  border-color: #dc2626;
}
</style>
