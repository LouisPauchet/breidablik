<template>
  <div>
    <h1>Calendar</h1>
    <p class="muted">
      Events and a combined view are coming soon. For now: who's away and when.
    </p>

    <h2>Away</h2>
    <p v-if="!absences.absences.length" class="muted">Nobody has marked themselves away.</p>
    <ul class="absence-list">
      <li v-for="absence in absences.absences" :key="absence.id" class="absence-row">
        <div>
          <strong>{{ members.nameOf(absence.user_id) }}</strong>
          {{ formatDate(absence.start_date) }} &ndash; {{ formatDate(absence.end_date) }}
          <span v-if="absence.reason" class="muted">({{ absence.reason }})</span>
        </div>
        <button v-if="absence.user_id === authStore.user?.id" type="button" @click="onDelete(absence.id)">
          Remove
        </button>
      </li>
    </ul>

    <h2>Mark yourself away</h2>
    <form class="card" @submit.prevent="submit">
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
const members = useMembersStore()
const authStore = useAuthStore()

await Promise.all([members.ensureLoaded(), absences.fetchAbsences()])

const today = new Date().toISOString().slice(0, 10)
const startDate = ref(today)
const endDate = ref(today)
const reason = ref('')
const loading = ref(false)
const error = ref('')

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

async function submit() {
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

async function onDelete(id: string) {
  await absences.deleteAbsence(id)
}
</script>

<style scoped>
.muted {
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
