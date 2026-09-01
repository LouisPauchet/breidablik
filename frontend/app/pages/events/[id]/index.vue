<template>
  <div v-if="event">
    <PageHeader :title="event.title" back="/events">
      <NuxtLink :to="`/events/${event.id}/edit`" class="btn-primary">Edit</NuxtLink>
    </PageHeader>

    <div class="info-card">
      <div><span class="type-badge">{{ event.event_type }}</span></div>
      <div>{{ formatDateTime(event.start_at) }}<span v-if="event.end_at"> &ndash; {{ formatDateTime(event.end_at) }}</span></div>
      <div v-if="event.location">{{ event.location }}</div>
      <p v-if="event.description">{{ event.description }}</p>
    </div>

    <h2>Are you going?</h2>
    <div class="rsvp-buttons">
      <button
        v-for="option in (['yes', 'maybe', 'no'] as const)"
        :key="option"
        type="button"
        :class="{ selected: myRsvp === option }"
        @click="onRsvp(option)"
      >
        {{ option }}
      </button>
    </div>

    <ul class="rsvp-summary">
      <li v-for="row in rsvpByMember" :key="row.userId" :class="{ pending: !row.status }">
        {{ row.name }}: <strong>{{ row.status ?? 'no response yet' }}</strong>
      </li>
    </ul>

    <div v-if="seriesSiblings.length" class="series-block">
      <h2>Also in this series</h2>
      <ul class="event-list">
        <li v-for="sibling in seriesSiblings" :key="sibling.id">
          <NuxtLink :to="`/events/${sibling.id}`">{{ sibling.title }} &mdash; {{ formatDateTime(sibling.start_at) }}</NuxtLink>
        </li>
      </ul>
    </div>

    <div class="danger-zone">
      <button type="button" class="danger" @click="onDelete">Delete event</button>
    </div>
  </div>
</template>

<script setup lang="ts">
const route = useRoute()
const router = useRouter()
const events = useEventsStore()
const members = useMembersStore()
const authStore = useAuthStore()

await members.ensureLoaded()
await events.fetchEvent(route.params.id as string)

const event = computed(() => events.current)

const seriesSiblings = ref<Awaited<ReturnType<typeof events.fetchEvents>>>([])
if (event.value?.series_id) {
  const siblings = await events.fetchEvents(event.value.series_id)
  seriesSiblings.value = siblings.filter((e) => e.id !== event.value?.id)
}

const myRsvp = computed(
  () => event.value?.rsvps.find((r) => r.user_id === authStore.user?.id)?.status ?? null
)

const rsvpByMember = computed(() => {
  const rsvps = event.value?.rsvps ?? []
  return members.members.map((m) => ({
    userId: m.id,
    name: m.display_name,
    status: rsvps.find((r) => r.user_id === m.id)?.status ?? null,
  }))
})

function formatDateTime(iso: string) {
  return new Date(iso).toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  })
}

async function onRsvp(status: 'yes' | 'maybe' | 'no') {
  await events.rsvp(route.params.id as string, status)
}

async function onDelete() {
  await events.deleteEvent(route.params.id as string)
  await router.push('/events')
}
</script>

<style scoped>
.btn-primary {
  background: var(--accent);
  color: white;
  padding: 0.4rem 0.8rem;
  border-radius: 0.5rem;
  text-decoration: none;
  font-size: 0.85rem;
  white-space: nowrap;
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

.type-badge {
  font-size: 0.7rem;
  color: var(--muted);
  border: 1px solid var(--border);
  border-radius: 999px;
  padding: 0.1rem 0.5rem;
  text-transform: capitalize;
}

.rsvp-buttons {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 1rem;
}

.rsvp-buttons button {
  flex: 1;
  padding: 0.6rem;
  border-radius: 0.5rem;
  border: 1px solid var(--border);
  background: var(--bg);
  color: var(--fg);
  text-transform: capitalize;
}

.rsvp-buttons button.selected {
  background: var(--accent);
  border-color: var(--accent);
  color: white;
}

.rsvp-summary {
  list-style: none;
  padding: 0;
  margin: 0 0 1.5rem;
  font-size: 0.9rem;
  color: var(--fg);
}

.rsvp-summary li.pending {
  color: var(--muted);
}

.series-block {
  margin-bottom: 1.5rem;
}

.event-list {
  list-style: none;
  padding: 0;
  margin: 0;
  font-size: 0.9rem;
}

.event-list a {
  color: var(--fg);
}

.danger-zone button.danger {
  padding: 0.55rem 0.9rem;
  border-radius: 0.5rem;
  border: 1px solid #dc2626;
  background: var(--bg);
  color: #dc2626;
}
</style>
