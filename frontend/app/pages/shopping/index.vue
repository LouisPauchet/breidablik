<template>
  <div>
    <h1>Shopping</h1>

    <p v-if="!shopping.lists.length" class="muted">No lists yet.</p>
    <ul class="list-cards">
      <li v-for="list in shopping.lists" :key="list.id">
        <NuxtLink :to="`/shopping/${list.id}`" class="list-card">
          <div class="list-title">
            {{ list.name }}
            <span v-if="list.owner_user_id" class="badge private">private</span>
            <span v-else class="badge shared">shared</span>
          </div>
          <div class="list-meta">{{ list.items.filter((i) => !i.is_checked).length }} item(s) left</div>
        </NuxtLink>
      </li>
    </ul>

    <h2>New list</h2>
    <form class="card" @submit.prevent="submit">
      <label>
        Name
        <input v-model="name" required />
      </label>
      <label class="checkbox-row">
        <input v-model="isPrivate" type="checkbox" />
        Private (only visible to me)
      </label>
      <label v-if="!isPrivate">
        Notify whoever's on this duty when items are added (optional)
        <select v-model="dutyId">
          <option value="">No duty</option>
          <option v-for="d in duties.duties" :key="d.id" :value="d.id">{{ d.title }}</option>
        </select>
      </label>
      <p v-if="error" class="error">{{ error }}</p>
      <button type="submit" class="submit-btn" :disabled="loading">Create list</button>
    </form>
  </div>
</template>

<script setup lang="ts">
const shopping = useShoppingStore()
const duties = useDutiesStore()

await Promise.all([shopping.fetchLists(), duties.fetchDuties()])

const name = ref('')
const isPrivate = ref(false)
const dutyId = ref('')
const loading = ref(false)
const error = ref('')

async function submit() {
  error.value = ''
  loading.value = true
  try {
    await shopping.createList({
      name: name.value,
      is_private: isPrivate.value,
      duty_id: isPrivate.value ? null : dutyId.value || null,
    })
    name.value = ''
    isPrivate.value = false
    dutyId.value = ''
  } catch {
    error.value = 'Could not create that list — check the fields and try again.'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.muted {
  color: var(--muted);
}

.list-cards {
  list-style: none;
  padding: 0;
  margin: 0 0 1.5rem;
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
}

.list-card {
  display: block;
  border: 1px solid var(--border);
  border-radius: 0.75rem;
  padding: 0.9rem;
  text-decoration: none;
  color: var(--fg);
}

.list-title {
  font-weight: 600;
  margin-bottom: 0.25rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.badge {
  font-size: 0.7rem;
  font-weight: 400;
  border-radius: 999px;
  padding: 0.1rem 0.5rem;
}

.badge.shared {
  background: #0f766e;
  color: white;
}

.badge.private {
  border: 1px solid var(--border);
  color: var(--muted);
}

.list-meta {
  font-size: 0.85rem;
  color: var(--muted);
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

.checkbox-row {
  flex-direction: row;
  align-items: center;
  gap: 0.5rem;
}

input,
select {
  padding: 0.6rem;
  border-radius: 0.5rem;
  border: 1px solid var(--border);
  background: var(--bg);
  color: var(--fg);
  font-size: 1rem;
  font-family: inherit;
}

.checkbox-row input {
  width: auto;
  padding: 0;
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
