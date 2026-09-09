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
const loading = ref(false)
const error = ref('')

async function submit() {
  error.value = ''
  loading.value = true
  try {
    await contests.createContest({ title: title.value, description: description.value || null, icon: icon.value })
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
