<template>
  <div v-if="event">
    <PageHeader title="Edit event" :back="`/events/${event.id}`" />
    <form class="card" @submit.prevent="submit">
      <label>
        Title
        <input v-model="title" required />
      </label>
      <label>
        Type
        <select v-model="eventType">
          <option value="dinner">Dinner</option>
          <option value="party">Party</option>
          <option value="meeting">Meeting</option>
          <option value="other">Other</option>
        </select>
      </label>
      <label>
        Description
        <textarea v-model="description" rows="2" />
      </label>
      <label>
        Location
        <input v-model="location" />
      </label>
      <label>
        Starts
        <input v-model="startAt" type="datetime-local" required />
      </label>
      <label>
        Ends (optional)
        <input v-model="endAt" type="datetime-local" />
      </label>

      <fieldset>
        <legend>Series (optional)</legend>
        <select v-model="selectedSeriesId">
          <option value="">No series</option>
          <option v-for="s in events.series" :key="s.id" :value="s.id">{{ s.name }}</option>
        </select>
      </fieldset>

      <p v-if="error" class="error">{{ error }}</p>
      <button type="submit" class="submit-btn" :disabled="loading">Save changes</button>
    </form>
  </div>
</template>

<script setup lang="ts">
const route = useRoute()
const router = useRouter()
const events = useEventsStore()

const eventId = route.params.id as string

await events.fetchSeries()
await events.fetchEvent(eventId)

const event = computed(() => events.current)

function toLocalInputValue(iso: string): string {
  const d = new Date(iso)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}

const title = ref(event.value?.title ?? '')
const eventType = ref<'dinner' | 'party' | 'meeting' | 'other'>(event.value?.event_type ?? 'other')
const description = ref(event.value?.description ?? '')
const location = ref(event.value?.location ?? '')
const startAt = ref(event.value ? toLocalInputValue(event.value.start_at) : '')
const endAt = ref(event.value?.end_at ? toLocalInputValue(event.value.end_at) : '')
const selectedSeriesId = ref(event.value?.series_id ?? '')
const loading = ref(false)
const error = ref('')

function toIso(localValue: string) {
  return new Date(localValue).toISOString()
}

async function submit() {
  error.value = ''
  loading.value = true
  try {
    await events.updateEvent(eventId, {
      title: title.value,
      event_type: eventType.value,
      description: description.value || null,
      location: location.value || null,
      start_at: toIso(startAt.value),
      end_at: endAt.value ? toIso(endAt.value) : null,
      series_id: selectedSeriesId.value || null,
    })
    await router.push(`/events/${eventId}`)
  } catch {
    error.value = 'Could not save changes. Check the fields and try again.'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.card {
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
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

input,
select,
textarea {
  padding: 0.6rem;
  border-radius: 0.5rem;
  border: 1px solid var(--border);
  background: var(--bg);
  color: var(--fg);
  font-size: 1rem;
  font-family: inherit;
}

fieldset {
  border: 1px solid var(--border);
  border-radius: 0.5rem;
  padding: 0.75rem;
}

legend {
  font-size: 0.85rem;
  color: var(--muted);
  padding: 0 0.3rem;
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
