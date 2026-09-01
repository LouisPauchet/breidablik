<template>
  <div>
    <PageHeader title="Calendar">
      <NuxtLink to="/events/new" class="btn-primary">+ New event</NuxtLink>
    </PageHeader>

    <div class="view-toggle">
      <button
        v-for="mode in (['month', 'week', 'agenda'] as const)"
        :key="mode"
        type="button"
        :class="{ active: viewMode === mode }"
        @click="viewMode = mode"
      >
        {{ mode }}
      </button>
    </div>

    <template v-if="viewMode === 'agenda'">
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
    </template>

    <template v-else>
      <div class="grid-nav">
        <button type="button" class="nav-btn" aria-label="Previous" @click="onPrev">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
            <path d="M15 18l-6-6 6-6" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" />
          </svg>
        </button>
        <div class="grid-label">
          <strong>{{ gridLabel }}</strong>
          <button type="button" class="today-btn" @click="onToday">Today</button>
        </div>
        <button type="button" class="nav-btn" aria-label="Next" @click="onNext">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
            <path d="M9 18l6-6-6-6" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" />
          </svg>
        </button>
      </div>

      <div class="weekday-row">
        <span v-for="w in weekdayLabels" :key="w">{{ w }}</span>
      </div>
      <div class="day-grid" :class="viewMode">
        <button
          v-for="day in gridDays"
          :key="day.iso"
          type="button"
          class="day-cell"
          :class="{ today: day.iso === todayIso, selected: day.iso === selectedDate, outside: !day.inCurrentPeriod }"
          @click="selectedDate = day.iso"
        >
          <span class="day-number">{{ day.dayNumber }}</span>
          <span class="dots">
            <span v-for="kind in dotKindsForDate(day.iso)" :key="kind" class="dot" :class="kind" />
          </span>
        </button>
      </div>

      <h3 class="selected-label">{{ selectedDateLabel }}</h3>
      <p v-if="!selectedEntries.length" class="muted">Nothing that day.</p>
      <ul class="agenda-list">
        <li v-for="entry in selectedEntries" :key="entry.key" class="agenda-row">
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
    </template>

    <h2>Away</h2>
    <p v-if="!absences.absences.length" class="muted">Nobody has marked themselves away.</p>
    <ul class="absence-list">
      <li v-for="absence in absences.absences" :key="absence.id" class="absence-row">
        <div>
          <strong>{{ members.nameOf(absence.user_id) }}</strong>
          {{ formatDate(absence.start_date) }} &ndash; {{ formatDate(absence.end_date) }}
          <span v-if="absence.reason" class="muted">({{ absence.reason }})</span>
          <span v-if="absence.auto_reassign" class="badge">auto-reassigned</span>
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
      <label class="checkbox-row">
        <input v-model="autoReassign" type="checkbox" />
        Auto-reassign my duties while I'm away
      </label>
      <p class="muted small">
        Hands any of your duty occurrences in this window to the next person in the rotation
        who isn't also away, instead of just flagging them for someone to swap by hand.
      </p>
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

interface UpcomingOccurrence {
  duty_id: string
  duty_title: string
  due_date: string
  assigned_user_id: string
  is_done: boolean
}

const DEFAULT_HORIZON_DAYS = 56
const upcomingOccurrences = ref<UpcomingOccurrence[]>(
  await $fetch<UpcomingOccurrence[]>('/api/duties/occurrences/upcoming')
)
let fetchedHorizonDays = DEFAULT_HORIZON_DAYS

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

function pad2(n: number) {
  return String(n).padStart(2, '0')
}

function toIso(d: Date): string {
  return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`
}

const now = new Date()
const todayDate = new Date(now.getFullYear(), now.getMonth(), now.getDate())
const todayIso = toIso(todayDate)

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

  for (const occ of upcomingOccurrences.value) {
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

// --- Month / week grid -----------------------------------------------------

const viewMode = ref<'month' | 'week' | 'agenda'>('month')
const anchor = ref(new Date(todayDate))
const selectedDate = ref(todayIso)

const weekdayLabels = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

function mondayIndex(d: Date) {
  return (d.getDay() + 6) % 7
}

function startOfWeek(d: Date): Date {
  const start = new Date(d)
  start.setDate(d.getDate() - mondayIndex(d))
  return start
}

function addDays(d: Date, n: number): Date {
  const copy = new Date(d)
  copy.setDate(copy.getDate() + n)
  return copy
}

function addMonths(d: Date, n: number): Date {
  return new Date(d.getFullYear(), d.getMonth() + n, 1)
}

interface GridDay {
  iso: string
  dayNumber: number
  inCurrentPeriod: boolean
}

const gridDays = computed<GridDay[]>(() => {
  if (viewMode.value === 'week') {
    const start = startOfWeek(anchor.value)
    return Array.from({ length: 7 }, (_, i) => {
      const d = addDays(start, i)
      return { iso: toIso(d), dayNumber: d.getDate(), inCurrentPeriod: true }
    })
  }
  const firstOfMonth = new Date(anchor.value.getFullYear(), anchor.value.getMonth(), 1)
  const start = startOfWeek(firstOfMonth)
  return Array.from({ length: 42 }, (_, i) => {
    const d = addDays(start, i)
    return {
      iso: toIso(d),
      dayNumber: d.getDate(),
      inCurrentPeriod: d.getMonth() === anchor.value.getMonth(),
    }
  })
})

const gridLabel = computed(() => {
  if (viewMode.value === 'week') {
    const start = startOfWeek(anchor.value)
    const end = addDays(start, 6)
    const sameMonth = start.getMonth() === end.getMonth()
    const startLabel = start.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
    const endLabel = end.toLocaleDateString(
      undefined,
      sameMonth ? { day: 'numeric', year: 'numeric' } : { month: 'short', day: 'numeric', year: 'numeric' }
    )
    return `${startLabel} - ${endLabel}`
  }
  return anchor.value.toLocaleDateString(undefined, { month: 'long', year: 'numeric' })
})

function onPrev() {
  anchor.value = viewMode.value === 'week' ? addDays(anchor.value, -7) : addMonths(anchor.value, -1)
}

function onNext() {
  anchor.value = viewMode.value === 'week' ? addDays(anchor.value, 7) : addMonths(anchor.value, 1)
}

function onToday() {
  anchor.value = new Date(todayDate)
  selectedDate.value = todayIso
}

const selectedDateLabel = computed(() =>
  new Date(selectedDate.value).toLocaleDateString(undefined, {
    weekday: 'long',
    month: 'long',
    day: 'numeric',
  })
)

function entriesForDate(dateIso: string): AgendaEntry[] {
  const entries: AgendaEntry[] = []
  const d = new Date(dateIso)
  const monthDay = dateIso.slice(5, 10)

  for (const occ of upcomingOccurrences.value) {
    if (occ.due_date !== dateIso) continue
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
    if (task.due_date !== dateIso) continue
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
    const eventDate = new Date(event.start_at)
    if (toIso(eventDate) !== dateIso) continue
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
    if (dateIso < absence.start_date || dateIso > absence.end_date) continue
    entries.push({
      key: `away-${absence.id}-${dateIso}`,
      date: d,
      kind: 'away',
      title: `${members.nameOf(absence.user_id)} away`,
      detail: absence.reason ?? '',
      whenLabel: `${formatDate(absence.start_date)} - ${formatDate(absence.end_date)}`,
    })
  }
  for (const member of members.members) {
    if (!member.birthday || member.birthday.slice(5, 10) !== monthDay) continue
    entries.push({
      key: `birthday-${member.id}-${dateIso}`,
      date: d,
      kind: 'birthday',
      title: `${member.display_name}'s birthday`,
      detail: '',
      whenLabel: formatDate(dateIso),
    })
  }
  return entries
}

function dotKindsForDate(dateIso: string): string[] {
  return [...new Set(entriesForDate(dateIso).map((e) => e.kind))]
}

const selectedEntries = computed(() => entriesForDate(selectedDate.value))

// The occurrences feed defaults to an 8-week horizon (see backend DEFAULT_HORIZON_DAYS) —
// widen it on demand whenever the grid is navigated further out than what's already fetched,
// rather than fetching a large horizon unconditionally on every load.
watch(
  gridDays,
  async (days) => {
    if (!days.length) return
    const lastIso = days[days.length - 1]!.iso
    const daysOut = Math.ceil((new Date(lastIso).getTime() - todayDate.getTime()) / 86400000)
    if (daysOut <= fetchedHorizonDays) return
    const horizon = Math.min(730, daysOut + 14)
    upcomingOccurrences.value = await $fetch<UpcomingOccurrence[]>('/api/duties/occurrences/upcoming', {
      query: { horizon_days: horizon },
    })
    fetchedHorizonDays = horizon
  },
  { immediate: true }
)

// --- Away form ---------------------------------------------------------

const startDate = ref(new Date().toISOString().slice(0, 10))
const endDate = ref(new Date().toISOString().slice(0, 10))
const reason = ref('')
const autoReassign = ref(false)
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
      auto_reassign: autoReassign.value,
    })
    reason.value = ''
    if (autoReassign.value) {
      // Reassignment happens server-side at creation time — refetch so the grid/agenda
      // reflect the new assignee immediately instead of showing the stale one.
      upcomingOccurrences.value = await $fetch<UpcomingOccurrence[]>('/api/duties/occurrences/upcoming', {
        query: { horizon_days: fetchedHorizonDays },
      })
    }
    autoReassign.value = false
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

.small {
  font-size: 0.8rem;
}

.view-toggle {
  display: flex;
  gap: 0.3rem;
  background: var(--border);
  border-radius: 0.6rem;
  padding: 0.2rem;
  margin-bottom: 1rem;
}

.view-toggle button {
  flex: 1;
  padding: 0.4rem;
  border: none;
  border-radius: 0.45rem;
  background: transparent;
  color: var(--fg);
  text-transform: capitalize;
  font-size: 0.85rem;
}

.view-toggle button.active {
  background: var(--bg);
  font-weight: 600;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.12);
}

.grid-nav {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 0.6rem;
}

.nav-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 2.25rem;
  height: 2.25rem;
  border: none;
  background: none;
  color: var(--link);
  flex-shrink: 0;
}

.grid-label {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  font-size: 1rem;
}

.today-btn {
  padding: 0.2rem 0.55rem;
  border-radius: 999px;
  border: 1px solid var(--border);
  background: var(--bg);
  color: var(--fg);
  font-size: 0.75rem;
}

.weekday-row {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  text-align: center;
  font-size: 0.72rem;
  color: var(--muted);
  margin-bottom: 0.3rem;
}

.day-grid {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 0.2rem;
  margin-bottom: 1rem;
}

.day-cell {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: flex-start;
  gap: 0.2rem;
  aspect-ratio: 1;
  border: 1px solid transparent;
  border-radius: 0.5rem;
  background: none;
  color: var(--fg);
  padding: 0.3rem 0.1rem;
  -webkit-tap-highlight-color: transparent;
}

.day-grid.week .day-cell {
  aspect-ratio: unset;
  min-height: 3.5rem;
}

.day-cell.outside {
  color: var(--muted);
  opacity: 0.45;
}

.day-cell.today .day-number {
  background: var(--accent);
  color: white;
  border-radius: 999px;
}

.day-cell.selected {
  border-color: var(--accent);
}

.day-number {
  font-size: 0.85rem;
  width: 1.6rem;
  height: 1.6rem;
  display: flex;
  align-items: center;
  justify-content: center;
}

.dots {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 0.15rem;
  min-height: 0.4rem;
}

.dot {
  width: 0.35rem;
  height: 0.35rem;
  border-radius: 999px;
}

.dot.duty {
  background: #0f766e;
}

.dot.task {
  background: #2563eb;
}

.dot.event {
  background: #9333ea;
}

.dot.away {
  background: #d97706;
}

.dot.birthday {
  background: #db2777;
}

.selected-label {
  margin-bottom: 0.5rem;
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

.absence-row .badge {
  margin-left: 0.4rem;
  font-size: 0.65rem;
  background: var(--accent);
  color: white;
  padding: 0.1rem 0.4rem;
  border-radius: 999px;
  white-space: nowrap;
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

.checkbox-row {
  flex-direction: row;
  align-items: center;
  gap: 0.5rem;
}

.checkbox-row input {
  width: auto;
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
