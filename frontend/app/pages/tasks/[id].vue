<template>
  <div v-if="task">
    <PageHeader title="Edit task" back="/tasks" />
    <form class="card" @submit.prevent="submit">
      <label>
        Title
        <input v-model="title" required />
      </label>
      <label>
        Description
        <textarea v-model="description" rows="2" />
      </label>
      <label>
        Due date (optional)
        <input v-model="dueDate" type="date" />
      </label>

      <fieldset>
        <legend>Who's doing it?</legend>
        <div class="member-picker">
          <button
            v-for="m in members.members"
            :key="m.id"
            type="button"
            class="member-chip"
            :class="{ selected: selectedIds.includes(m.id) }"
            @click="toggleMember(m.id)"
          >
            {{ m.display_name }}
          </button>
        </div>
      </fieldset>

      <p v-if="error" class="error">{{ error }}</p>
      <button type="submit" class="submit-btn" :disabled="loading || !selectedIds.length">
        Save changes
      </button>
    </form>
  </div>
</template>

<script setup lang="ts">
const route = useRoute()
const router = useRouter()
const tasks = useTasksStore()
const members = useMembersStore()

const taskId = route.params.id as string

await Promise.all([members.ensureLoaded(), tasks.fetchTasks()])

const task = computed(() => tasks.tasks.find((t) => t.id === taskId) ?? null)
if (!task.value) {
  await router.replace('/tasks')
}

const title = ref(task.value?.title ?? '')
const description = ref(task.value?.description ?? '')
const dueDate = ref(task.value?.due_date ?? '')
const selectedIds = ref<string[]>(task.value?.assignee_user_ids ?? [])
const loading = ref(false)
const error = ref('')

function toggleMember(id: string) {
  const idx = selectedIds.value.indexOf(id)
  if (idx === -1) selectedIds.value.push(id)
  else selectedIds.value.splice(idx, 1)
}

async function submit() {
  error.value = ''
  loading.value = true
  try {
    await tasks.updateTask(taskId, {
      title: title.value,
      description: description.value || null,
      due_date: dueDate.value || null,
      assignee_user_ids: selectedIds.value,
    })
    await router.push('/tasks')
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

.member-picker {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
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
