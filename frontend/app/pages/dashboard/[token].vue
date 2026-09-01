<template>
  <div class="dashboard">
    <template v-if="loadError">
      <div class="error-screen">
        <p>This dashboard link isn't valid.</p>
        <p class="muted">Ask someone in the household for the current link from their Profile page.</p>
      </div>
    </template>

    <template v-else-if="data">
      <header class="dash-header">
        <h1>Breidablik</h1>
        <p class="date">{{ todayLabel }}</p>
      </header>

      <div class="dash-grid">
        <section class="panel">
          <h2>On duty today</h2>
          <p v-if="!data.on_duty_today.length" class="muted">No active duties yet.</p>
          <ul class="on-duty-list">
            <li v-for="entry in data.on_duty_today" :key="entry.duty_id">
              <Avatar
                :user-id="entry.assignee_user_id"
                :name="entry.assignee_display_name"
                :avatar-updated-at="entry.assignee_avatar_updated_at"
                :src-override="avatarUrl(entry.assignee_user_id)"
                :size="56"
              />
              <div class="on-duty-text">
                <strong>{{ entry.duty_title }}</strong>
                <span>{{ entry.assignee_display_name }}</span>
              </div>
            </li>
          </ul>
        </section>

        <section class="panel">
          <h2>Coming up</h2>
          <p v-if="!data.upcoming.length" class="muted">Nothing in the next few days.</p>
          <ul class="agenda-list">
            <li v-for="entry in data.upcoming" :key="entry.key">
              <span class="dot" :class="entry.kind" />
              <div class="agenda-text">
                <strong>{{ entry.title }}</strong>
                <span v-if="entry.detail" class="muted">{{ entry.detail }}</span>
              </div>
              <span class="when">{{ whenLabel(entry) }}</span>
            </li>
          </ul>
        </section>
      </div>

      <footer class="dash-footer">
        <blockquote class="quote">
          <p>&ldquo;{{ data.quote.text }}&rdquo;</p>
          <cite>&mdash; {{ data.quote.author }}</cite>
        </blockquote>

        <section class="panel activity">
          <h2>Recent activity</h2>
          <p v-if="!data.activity.length" class="muted">Nothing yet.</p>
          <ul class="activity-list">
            <li v-for="(entry, i) in data.activity" :key="i">
              <span class="muted small">{{ activityWhenLabel(entry.at) }}</span>
              {{ entry.text }}
            </li>
          </ul>
        </section>
      </footer>
    </template>
  </div>
</template>

<script setup lang="ts">
definePageMeta({ fullBleed: true })

interface DashboardOnDuty {
  duty_id: string
  duty_title: string
  assignee_user_id: string
  assignee_display_name: string
  assignee_avatar_updated_at: string | null
}

interface DashboardAgendaEntry {
  key: string
  kind: 'duty' | 'task' | 'event' | 'away' | 'birthday'
  title: string
  detail: string
  at: string
}

interface DashboardActivityEntry {
  at: string
  text: string
}

interface DashboardData {
  generated_at: string
  quote: { text: string; author: string }
  on_duty_today: DashboardOnDuty[]
  upcoming: DashboardAgendaEntry[]
  activity: DashboardActivityEntry[]
}

const route = useRoute()
const token = route.params.token as string

const data = ref<DashboardData | null>(null)
const loadError = ref(false)

const REFRESH_INTERVAL_MS = 5 * 60 * 1000
let refreshTimer: ReturnType<typeof setInterval> | undefined

async function load() {
  try {
    data.value = await $fetch<DashboardData>(`/api/dashboard/${token}`)
    loadError.value = false
  } catch {
    loadError.value = true
  }
}

await load()

onMounted(() => {
  refreshTimer = setInterval(load, REFRESH_INTERVAL_MS)
})

onUnmounted(() => {
  if (refreshTimer) clearInterval(refreshTimer)
})

function avatarUrl(userId: string): string {
  return `/api/dashboard/${token}/avatar/${userId}`
}

const todayLabel = computed(() =>
  new Date().toLocaleDateString(undefined, { weekday: 'long', month: 'long', day: 'numeric' })
)

function whenLabel(entry: DashboardAgendaEntry): string {
  const d = new Date(entry.at)
  const today = new Date()
  const isToday = d.toDateString() === today.toDateString()
  const tomorrow = new Date(today)
  tomorrow.setDate(tomorrow.getDate() + 1)
  const isTomorrow = d.toDateString() === tomorrow.toDateString()

  const dayLabel = isToday
    ? 'Today'
    : isTomorrow
      ? 'Tomorrow'
      : d.toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' })

  if (entry.kind !== 'event') return dayLabel
  return `${dayLabel}, ${d.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' })}`
}

function activityWhenLabel(at: string): string {
  return new Date(at).toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  })
}
</script>

<style scoped>
.dashboard {
  min-height: 100vh;
  padding: 2.5rem 3rem;
  font-size: 1.1rem;
  color: var(--fg);
  background: var(--bg);
}

.error-screen {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  gap: 0.5rem;
}

.muted {
  color: var(--muted);
}

.small {
  font-size: 0.8em;
}

.dash-header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin-bottom: 2rem;
}

.dash-header h1 {
  margin: 0;
  font-size: 2rem;
  color: var(--accent);
}

.dash-header .date {
  margin: 0;
  font-size: 1.4rem;
  color: var(--muted);
}

.dash-grid {
  display: grid;
  grid-template-columns: 1fr 1.2fr;
  gap: 2rem;
  margin-bottom: 2rem;
}

.panel {
  border: 1px solid var(--border);
  border-radius: 1rem;
  padding: 1.5rem;
}

.panel h2 {
  margin-top: 0;
  font-size: 1.3rem;
}

.on-duty-list,
.agenda-list,
.activity-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.on-duty-list li {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.on-duty-text {
  display: flex;
  flex-direction: column;
  font-size: 1.15rem;
}

.on-duty-text span {
  color: var(--muted);
  font-size: 0.95rem;
}

.agenda-list li {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.agenda-text {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-width: 0;
}

.agenda-text span {
  font-size: 0.9rem;
}

.when {
  color: var(--muted);
  font-size: 0.9rem;
  white-space: nowrap;
}

.dot {
  width: 0.7rem;
  height: 0.7rem;
  border-radius: 999px;
  flex-shrink: 0;
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

.dash-footer {
  display: grid;
  grid-template-columns: 1fr 1.2fr;
  gap: 2rem;
  align-items: start;
}

.quote {
  margin: 0;
  padding: 1.5rem;
  font-style: italic;
  font-size: 1.3rem;
}

.quote cite {
  display: block;
  margin-top: 0.75rem;
  font-style: normal;
  font-size: 1rem;
  color: var(--muted);
}

.activity-list li {
  font-size: 0.95rem;
  display: flex;
  flex-direction: column;
  gap: 0.1rem;
}

@media (max-width: 900px) {
  .dashboard {
    padding: 1.5rem;
  }

  .dash-grid,
  .dash-footer {
    grid-template-columns: 1fr;
  }
}
</style>
