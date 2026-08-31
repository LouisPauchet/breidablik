<template>
  <div>
    <h1>New event</h1>
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
        <button type="button" class="link-btn" @click="showNewSeries = !showNewSeries">
          {{ showNewSeries ? 'Cancel' : '+ New series' }}
        </button>
        <div v-if="showNewSeries" class="new-series-row">
          <input v-model="newSeriesName" placeholder="e.g. MasterChef Dinners" />
          <button type="button" @click="onCreateSeries">Create</button>
        </div>
      </fieldset>

      <p v-if="error" class="error">{{ error }}</p>
      <button type="submit" class="submit-btn" :disabled="loading">Create event</button>
    </form>
  </div>
</template>

<script setup lang="ts">
const events = useEventsStore()
const router = useRouter()

await events.fetchSeries()

const title = ref('')
const eventType = ref<'dinner' | 'party' | 'meeting' | 'other'>('other')
const description = ref('')
const location = ref('')
const startAt = ref('')
const endAt = ref('')
const selectedSeriesId = ref('')
const showNewSeries = ref(false)
const newSeriesName = ref('')
const loading = ref(false)
const error = ref('')

async function onCreateSeries() {
  if (!newSeriesName.value.trim()) return
  const created = await events.createSeries(newSeriesName.value.trim())
  selectedSeriesId.value = created.id
  newSeriesName.value = ''
  showNewSeries.value = false
}

function toIso(localValue: string) {
  return new Date(localValue).toISOString()
}

async function submit() {
  error.value = ''
  loading.value = true
  try {
    const event = await events.createEvent({
      title: title.value,
      event_type: eventType.value,
      description: description.value || null,
      location: location.value || null,
      start_at: toIso(startAt.value),
      end_at: endAt.value ? toIso(endAt.value) : null,
      series_id: selectedSeriesId.value || null,
    })
    await router.push(`/events/${event.id}`)
  } catch {
    error.value = 'Could not create the event. Check the fields and try again.'
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
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

legend {
  font-size: 0.85rem;
  color: var(--muted);
  padding: 0 0.3rem;
}

.link-btn {
  background: none;
  border: none;
  color: var(--link);
  padding: 0;
  text-align: left;
  font-size: 0.85rem;
}

.new-series-row {
  display: flex;
  gap: 0.5rem;
}

.new-series-row input {
  flex: 1;
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
