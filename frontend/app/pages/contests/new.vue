<template>
  <div>
    <PageHeader title="New contest duty" back="/contests" />
    <form class="card" @submit.prevent="submit">
      <label>
        Title
        <input v-model="title" placeholder="e.g. Empty the dishwasher" required />
      </label>
      <label>
        Description (optional)
        <textarea v-model="description" rows="2" />
      </label>
      <label>
        Icon
        <input v-model="icon" placeholder="🍽️" maxlength="8" required class="icon-input" />
      </label>

      <fieldset>
        <legend>Minimum wait between logs</legend>
        <div class="interval-row">
          <input v-model.number="intervalValue" type="number" min="0" />
          <select v-model="intervalUnit">
            <option value="minutes">minutes</option>
            <option value="hours">hours</option>
            <option value="days">days</option>
          </select>
        </div>
        <p class="muted small">
          Once anyone logs it, nobody can log it again until this much time has passed. Leave
          at 0 for no limit.
        </p>
      </fieldset>

      <label class="checkbox-row">
        <input v-model="showOnHome" type="checkbox" />
        Show on the home screen
      </label>

      <p class="muted small">
        No schedule, no assignee — anyone can log it whenever they do it, and this month's
        most frequent logger gets an award at the reveal.
      </p>
      <p v-if="error" class="error">{{ error }}</p>
      <button type="submit" class="submit-btn" :disabled="loading || !title || !icon">
        Create contest duty
      </button>
    </form>
  </div>
</template>

<script setup lang="ts">
const contests = useContestsStore()
const router = useRouter()

const title = ref('')
const description = ref('')
const icon = ref('')
const intervalValue = ref(0)
const intervalUnit = ref<'minutes' | 'hours' | 'days'>('hours')
const showOnHome = ref(false)
const loading = ref(false)
const error = ref('')

const MINUTES_PER_UNIT = { minutes: 1, hours: 60, days: 60 * 24 }

async function submit() {
  error.value = ''
  loading.value = true
  try {
    await contests.createContest({
      title: title.value,
      description: description.value || null,
      icon: icon.value,
      min_interval_minutes: Math.max(0, intervalValue.value) * MINUTES_PER_UNIT[intervalUnit.value],
      show_on_home: showOnHome.value,
    })
    await router.push('/contests')
  } catch {
    error.value = 'Could not create the contest duty. Check the fields and try again.'
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

.icon-input {
  width: 4rem;
  text-align: center;
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

.interval-row {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 0.4rem;
}

.interval-row input {
  width: 5rem;
}

.checkbox-row {
  flex-direction: row;
  align-items: center;
  gap: 0.5rem;
}

.checkbox-row input {
  width: auto;
}

fieldset p {
  margin: 0;
}

.muted {
  color: var(--muted);
}

.small {
  font-size: 0.8rem;
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
