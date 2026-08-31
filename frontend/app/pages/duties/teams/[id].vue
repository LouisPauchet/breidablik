<template>
  <div v-if="team">
    <PageHeader :title="team.name" back="/duties/teams" />
    <p v-if="team.description" class="muted">{{ team.description }}</p>

    <div class="info-card">
      <div>Rotates every <strong>{{ team.rotation_interval_days }}</strong> day(s)</div>
      <div>
        Member order: <strong>{{ team.members.map((m) => members.nameOf(m.user_id)).join(' -> ') }}</strong>
      </div>
      <div>Current period: {{ formatDate(team.current_period.start_date) }} &ndash; {{ formatDate(team.current_period.end_date) }}</div>
    </div>

    <h2>This period's assignments</h2>
    <p v-if="!team.current_assignments.length" class="muted">No duties attached yet.</p>
    <ul class="assignment-list">
      <li v-for="a in team.current_assignments" :key="a.duty_id">
        <NuxtLink :to="`/duties/${a.duty_id}`">{{ a.duty_title }}</NuxtLink>
        <span class="muted"> &rarr; {{ members.nameOf(a.assignee_user_id) }}</span>
      </li>
    </ul>

    <NuxtLink :to="`/duties/new?team_id=${team.id}`" class="btn-secondary">+ Add a duty to this team</NuxtLink>

    <h2>Members</h2>
    <div class="member-picker">
      <button
        v-for="m in members.members"
        :key="m.id"
        type="button"
        class="member-chip"
        :class="{ selected: memberDraft.includes(m.id) }"
        @click="toggleMember(m.id)"
      >
        {{ m.display_name }}
      </button>
    </div>
    <ol v-if="memberDraft.length" class="order-list">
      <li v-for="(id, i) in memberDraft" :key="id">
        <span>{{ members.nameOf(id) }}</span>
        <span class="order-actions">
          <button type="button" :disabled="i === 0" @click="moveUp(i)">↑</button>
          <button type="button" :disabled="i === memberDraft.length - 1" @click="moveDown(i)">↓</button>
        </span>
      </li>
    </ol>
    <button type="button" class="btn-secondary" :disabled="!memberDraft.length" @click="onSaveMembers">
      Save member changes
    </button>

    <div class="danger-zone">
      <button type="button" class="danger" @click="onDelete">Delete team</button>
      <p class="muted small">Deleting a team also deletes every duty attached to it.</p>
    </div>
  </div>
</template>

<script setup lang="ts">
const route = useRoute()
const router = useRouter()
const teams = useDutyTeamsStore()
const members = useMembersStore()

await members.ensureLoaded()
await teams.fetchTeam(route.params.id as string)

const team = computed(() => teams.current)
const memberDraft = ref<string[]>(team.value?.members.map((m) => m.user_id) ?? [])

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

function toggleMember(id: string) {
  const idx = memberDraft.value.indexOf(id)
  if (idx === -1) memberDraft.value.push(id)
  else memberDraft.value.splice(idx, 1)
}

function moveUp(i: number) {
  if (i === 0) return
  const arr = memberDraft.value
  ;[arr[i - 1], arr[i]] = [arr[i], arr[i - 1]]
}

function moveDown(i: number) {
  const arr = memberDraft.value
  if (i === arr.length - 1) return
  ;[arr[i], arr[i + 1]] = [arr[i + 1], arr[i]]
}

async function onSaveMembers() {
  await teams.updateMembers(route.params.id as string, memberDraft.value)
}

async function onDelete() {
  await teams.deleteTeam(route.params.id as string)
  await router.push('/duties/teams')
}
</script>

<style scoped>
.muted {
  color: var(--muted);
}

.small {
  font-size: 0.8rem;
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

.assignment-list {
  list-style: none;
  padding: 0;
  margin: 0 0 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.assignment-list a {
  color: var(--link);
  text-decoration: none;
}

.btn-secondary {
  display: inline-block;
  padding: 0.5rem 0.9rem;
  border-radius: 0.5rem;
  border: 1px solid var(--border);
  background: var(--bg);
  color: var(--fg);
  text-decoration: none;
  font-size: 0.85rem;
  margin-bottom: 1.5rem;
}

.member-picker {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
  margin-bottom: 0.5rem;
}

.member-chip {
  padding: 0.4rem 0.75rem;
  border-radius: 999px;
  border: 1px solid var(--border);
  background: var(--bg);
  color: var(--fg);
  font-size: 0.85rem;
}

.member-chip.selected {
  background: var(--accent);
  border-color: var(--accent);
  color: white;
}

.order-list {
  list-style: decimal;
  padding-left: 1.25rem;
  margin: 0.5rem 0;
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
}

.order-list li {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 0.9rem;
}

.order-actions button {
  padding: 0.15rem 0.5rem;
  margin-left: 0.25rem;
  border-radius: 0.35rem;
  border: 1px solid var(--border);
  background: var(--bg);
  color: var(--fg);
}

.danger-zone {
  margin-top: 2rem;
}

.danger-zone button.danger {
  padding: 0.55rem 0.9rem;
  border-radius: 0.5rem;
  border: 1px solid #dc2626;
  background: var(--bg);
  color: #dc2626;
}
</style>
