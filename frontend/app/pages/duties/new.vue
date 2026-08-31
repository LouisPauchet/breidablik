<template>
  <div>
    <h1>New duty</h1>
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
        Start date
        <input v-model="startDate" type="date" required />
      </label>

      <fieldset>
        <legend>How often does it need doing?</legend>
        <div class="interval-row">
          <input v-model.number="taskValue" type="number" min="1" required />
          <select v-model="taskUnit">
            <option value="days">days</option>
            <option value="weeks">weeks</option>
          </select>
        </div>
      </fieldset>

      <fieldset>
        <legend>How often does the responsible person change?</legend>
        <div class="interval-row">
          <input v-model.number="rotationValue" type="number" min="1" required />
          <select v-model="rotationUnit">
            <option value="days">days</option>
            <option value="weeks">weeks</option>
          </select>
        </div>
      </fieldset>

      <fieldset>
        <legend>Who's in the rotation? (tap to add, in order)</legend>
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
        <ol v-if="selectedIds.length" class="order-list">
          <li v-for="(id, i) in selectedIds" :key="id">
            <span>{{ members.nameOf(id) }}</span>
            <span class="order-actions">
              <button type="button" :disabled="i === 0" @click="moveUp(i)">↑</button>
              <button type="button" :disabled="i === selectedIds.length - 1" @click="moveDown(i)">↓</button>
            </span>
          </li>
        </ol>
      </fieldset>

      <p v-if="error" class="error">{{ error }}</p>
      <button type="submit" class="submit-btn" :disabled="loading || !selectedIds.length">
        Create duty
      </button>
    </form>
  </div>
</template>

<script setup lang="ts">
const members = useMembersStore()
const duties = useDutiesStore()
const router = useRouter()

await members.ensureLoaded()

const title = ref('')
const description = ref('')
const startDate = ref(new Date().toISOString().slice(0, 10))
const taskValue = ref(1)
const taskUnit = ref<'days' | 'weeks'>('weeks')
const rotationValue = ref(2)
const rotationUnit = ref<'days' | 'weeks'>('weeks')
const selectedIds = ref<string[]>([])
const loading = ref(false)
const error = ref('')

function toggleMember(id: string) {
  const idx = selectedIds.value.indexOf(id)
  if (idx === -1) selectedIds.value.push(id)
  else selectedIds.value.splice(idx, 1)
}

function moveUp(i: number) {
  if (i === 0) return
  const arr = selectedIds.value
  ;[arr[i - 1], arr[i]] = [arr[i], arr[i - 1]]
}

function moveDown(i: number) {
  const arr = selectedIds.value
  if (i === arr.length - 1) return
  ;[arr[i], arr[i + 1]] = [arr[i + 1], arr[i]]
}

function toDays(value: number, unit: 'days' | 'weeks') {
  return unit === 'weeks' ? value * 7 : value
}

async function submit() {
  error.value = ''
  loading.value = true
  try {
    const duty = await duties.createDuty({
      title: title.value,
      description: description.value || null,
      start_date: startDate.value,
      task_interval_days: toDays(taskValue.value, taskUnit.value),
      rotation_interval_days: toDays(rotationValue.value, rotationUnit.value),
      assignee_user_ids: selectedIds.value,
    })
    await router.push(`/duties/${duty.id}`)
  } catch {
    error.value = 'Could not create the duty. Check the fields and try again.'
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

.interval-row {
  display: flex;
  gap: 0.5rem;
}

.interval-row input {
  width: 5rem;
}

.member-picker {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
  margin-bottom: 0.5rem;
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

.order-list {
  list-style: decimal;
  padding-left: 1.25rem;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
}

.order-list li {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 0.9rem;
}

.order-actions button {
  padding: 0.15rem 0.5rem;
  margin-left: 0.25rem;
  border-radius: 0.35rem;
  border: 1px solid var(--border);
  background: var(--bg);
  color: var(--fg);
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
