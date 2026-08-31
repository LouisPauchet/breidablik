<template>
  <div>
    <header class="page-header">
      <h1>Calendar</h1>
      <NuxtLink to="/events/new" class="btn-primary">+ New event</NuxtLink>
    </header>

    <p v-if="!agenda.length" class="muted">Nothing coming up in the next 8 weeks.</p>
    <ul class="agenda-list">
      <li v-for="entry in agenda" :key="entry.key" class="agenda-row">
        <span class="kind-badge" :class="entry.kind">{{ entry.kind }}</span>
        <div class="agenda-body">
          <NuxtLink v-if="entry.href" :to="entry.href" class="agenda-title" :class="{ done: entry.done }">
            {{ entry.title }}
          </NuxtLink>
          <span v-else class="agenda-title" :class="{ done: entry.done }">{{ entry.title }}</span>
          <div class="agenda-meta">{{ entry.whenLabel }}<span v-if="entry.detail"> &middot; {{ entry.detail }}</span></div>
        </div>
      </li>
    </ul>

    <h2>Away</h2>
    <p v-if="!absences.absences.length" class="muted">Nobody has marked themselves away.</p>
    <ul class="absence-list">
      <li v-for="absence in absences.absences" :key="absence.id" class="absence-row">
        <div>
          <strong>{{ members.nameOf(absence.user_id) }}</strong>
          {{ formatDate(absence.start_date) }} &ndash; {{ formatDate(absence.end_date) }}
          <span v-if="absence.reason" class="muted">({{ absence.reason }})</span>
        </div>
        <button v-if="absence.user_id === authStore.user?.id" type="button" @click="onDeleteAbsence(absence.id)">
          Remove
        </button>
      </li>
    </ul>

    <h2>Mark yourself away</h2>
    <form class="card" @submit.prevent="submitAbsence">
      <label>
        From
        <input v-model="startDate" type="date" required />
      </label>
      <label>
        To
        <input v-model="endDate" type="date" required />
      </label>
      <label>
        Reason (optional)
        <input v-model="reason" placeholder="e.g. holiday" />
      </label>
      <p v-if="error" class="error">{{ error }}</p>
      <button type="submit" class="submit-btn" :disabled="loading">Add</button>
    </form>
  </div>
</template>

<script setup lang="ts">
const absences = useAbsencesStore()
const tasks = useTasksStore()
const events = useEventsStore()
const members = useMembersStore()
const authStore = useAuthStore()

await Promise.all([
  members.ensureLoaded(),
  absences.fetchAbsences(),
  tasks.fetchTasks(),
  events.fetchEvents(),
])

const upcomingOccurrences = await $fetch<
  { duty_id: string; duty_title: string; due_date: string; assigned_user_id: string; is_done: boolean }[]
>('/api/duties/occurrences/upcoming')

interface AgendaEntry {
  key: string
  date: Date
  kind: 'duty' | 'task' | 'event' | 'away' | 'birthday'
  title: string
  detail: string
  whenLabel: string
  done?: boolean
  href?: string
}

const today = new Date()
today.setHours(0, 0, 0, 0)
const windowStart = new Date(today)
windowStart.setDate(windowStart.getDate() - 1)
const windowEnd = new Date(today)
windowEnd.setDate(windowEnd.getDate() + 56)

function inWindow(d: Date) {
  return d >= windowStart && d <= windowEnd
}

function nextBirthdayOccurrence(birthdayIso: string, referenceDate: Date): Date {
  const birth = new Date(birthdayIso)
  const candidate = new Date(referenceDate.getFullYear(), birth.getMonth(), birth.getDate())
  if (candidate < referenceDate) candidate.setFullYear(candidate.getFullYear() + 1)
  return candidate
}

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

function formatDateTime(iso: string) {
  return new Date(iso).toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  })
}

const agenda = computed<AgendaEntry[]>(() => {
  const entries: AgendaEntry[] = []

  for (const occ of upcomingOccurrences) {
    const d = new Date(occ.due_date)
    if (!inWindow(d)) continue
    entries.push({
      key: `duty-${occ.duty_id}-${occ.due_date}`,
      date: d,
      kind: 'duty',
      title: occ.duty_title,
      detail: members.nameOf(occ.assigned_user_id),
      whenLabel: formatDate(occ.due_date),
      done: occ.is_done,
      href: `/duties/${occ.duty_id}`,
    })
  }

  for (const task of tasks.tasks) {
    if (!task.due_date) continue
    const d = new Date(task.due_date)
    if (!inWindow(d)) continue
    entries.push({
      key: `task-${task.id}`,
      date: d,
      kind: 'task',
      title: task.title,
      detail: task.assignee_user_ids.map((id) => members.nameOf(id)).join(', '),
      whenLabel: formatDate(task.due_date),
      done: task.is_done,
      href: '/tasks',
    })
  }

  for (const event of events.events) {
    const d = new Date(event.start_at)
    if (!inWindow(d)) continue
    entries.push({
      key: `event-${event.id}`,
      date: d,
      kind: 'event',
      title: event.title,
      detail: event.location ?? '',
      whenLabel: formatDateTime(event.start_at),
      href: `/events/${event.id}`,
    })
  }

  for (const absence of absences.absences) {
    const d = new Date(absence.start_date)
    if (!inWindow(d)) continue
    entries.push({
      key: `away-${absence.id}`,
      date: d,
      kind: 'away',
      title: `${members.nameOf(absence.user_id)} away`,
      detail: absence.reason ?? '',
      whenLabel: `${formatDate(absence.start_date)} - ${formatDate(absence.end_date)}`,
    })
  }

  for (const member of members.members) {
    if (!member.birthday) continue
    const next = nextBirthdayOccurrence(member.birthday, today)
    if (!inWindow(next)) continue
    entries.push({
      key: `birthday-${member.id}-${next.getFullYear()}`,
      date: next,
      kind: 'birthday',
      title: `${member.display_name}'s birthday`,
      detail: '',
      whenLabel: next.toLocaleDateString(undefined, { month: 'short', day: 'numeric' }),
    })
  }

  return entries.sort((a, b) => a.date.getTime() - b.date.getTime())
})

const startDate = ref(new Date().toISOString().slice(0, 10))
const endDate = ref(new Date().toISOString().slice(0, 10))
const reason = ref('')
const loading = ref(false)
const error = ref('')

async function submitAbsence() {
  error.value = ''
  loading.value = true
  try {
    await absences.createAbsence({
      start_date: startDate.value,
      end_date: endDate.value,
      reason: reason.value || null,
    })
    reason.value = ''
  } catch {
    error.value = 'Could not add that — check the dates and try again.'
  } finally {
    loading.value = false
  }
}

async function onDeleteAbsence(id: string) {
  await absences.deleteAbsence(id)
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
  font-size: 0.85rem;
  white-space: nowrap;
}

.muted {
  color: var(--muted);
}

.agenda-list {
  list-style: none;
  padding: 0;
  margin: 0 0 1.5rem;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.agenda-row {
  display: flex;
  align-items: flex-start;
  gap: 0.6rem;
  border: 1px solid var(--border);
  border-radius: 0.6rem;
  padding: 0.7rem;
}

.kind-badge {
  flex-shrink: 0;
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 0.02em;
  padding: 0.2rem 0.5rem;
  border-radius: 999px;
  color: white;
  margin-top: 0.1rem;
}

.kind-badge.duty {
  background: #0f766e;
}

.kind-badge.task {
  background: #2563eb;
}

.kind-badge.event {
  background: #9333ea;
}

.kind-badge.away {
  background: #d97706;
}

.kind-badge.birthday {
  background: #db2777;
}

.agenda-body {
  flex: 1;
  min-width: 0;
}

.agenda-title {
  display: block;
  font-weight: 600;
  color: var(--fg);
  text-decoration: none;
}

.agenda-title.done {
  text-decoration: line-through;
  color: var(--muted);
  font-weight: 400;
}

.agenda-meta {
  font-size: 0.8rem;
  color: var(--muted);
}

.absence-list {
  list-style: none;
  padding: 0;
  margin: 0 0 1.5rem;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.absence-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  border: 1px solid var(--border);
  border-radius: 0.6rem;
  padding: 0.7rem;
  font-size: 0.9rem;
}

.absence-row button {
  padding: 0.3rem 0.6rem;
  border-radius: 0.4rem;
  border: 1px solid var(--border);
  background: var(--bg);
  color: var(--fg);
  font-size: 0.8rem;
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
