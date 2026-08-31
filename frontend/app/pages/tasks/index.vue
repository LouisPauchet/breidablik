<template>
  <div>
    <PageHeader title="Tasks" />

    <p v-if="!tasks.tasks.length" class="muted">No tasks yet.</p>
    <ul class="task-list">
      <li v-for="task in tasks.tasks" :key="task.id" class="task-row">
        <label class="done-toggle">
          <input type="checkbox" :checked="task.is_done" @change="onToggle(task.id)" />
          <span :class="{ done: task.is_done }">{{ task.title }}</span>
        </label>
        <div class="task-meta">
          <span v-if="task.due_date">Due {{ formatDate(task.due_date) }}</span>
          <span>{{ task.assignee_user_ids.map((id) => members.nameOf(id)).join(', ') }}</span>
        </div>
        <button type="button" class="delete-btn" @click="onDelete(task.id)">Delete</button>
      </li>
    </ul>

    <h2>New task</h2>
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
        Add task
      </button>
    </form>
  </div>
</template>

<script setup lang="ts">
const tasks = useTasksStore()
const members = useMembersStore()

await Promise.all([members.ensureLoaded(), tasks.fetchTasks()])

const title = ref('')
const description = ref('')
const dueDate = ref('')
const selectedIds = ref<string[]>([])
const loading = ref(false)
const error = ref('')

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

function toggleMember(id: string) {
  const idx = selectedIds.value.indexOf(id)
  if (idx === -1) selectedIds.value.push(id)
  else selectedIds.value.splice(idx, 1)
}

async function onToggle(taskId: string) {
  await tasks.toggleDone(taskId)
}

async function onDelete(taskId: string) {
  await tasks.deleteTask(taskId)
}

async function submit() {
  error.value = ''
  loading.value = true
  try {
    await tasks.createTask({
      title: title.value,
      description: description.value || null,
      due_date: dueDate.value || null,
      assignee_user_ids: selectedIds.value,
    })
    title.value = ''
    description.value = ''
    dueDate.value = ''
    selectedIds.value = []
  } catch {
    error.value = 'Could not add that task — check the fields and try again.'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.muted {
  color: var(--muted);
}

.task-list {
  list-style: none;
  padding: 0;
  margin: 0 0 1.5rem;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.task-row {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  border: 1px solid var(--border);
  border-radius: 0.6rem;
  padding: 0.7rem;
  font-size: 0.9rem;
}

.done-toggle {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  flex: 1;
}

.done-toggle span.done {
  text-decoration: line-through;
  color: var(--muted);
}

.task-meta {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  font-size: 0.75rem;
  color: var(--muted);
  white-space: nowrap;
}

.delete-btn {
  padding: 0.3rem 0.6rem;
  border-radius: 0.4rem;
  border: 1px solid var(--border);
  background: var(--bg);
  color: #dc2626;
  font-size: 0.8rem;
}

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
