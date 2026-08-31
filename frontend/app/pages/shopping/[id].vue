<template>
  <div v-if="list">
    <PageHeader :title="list.name" back="/shopping" />

    <p v-if="list.duty_id" class="muted">
      Adding an item notifies whoever's on <strong>{{ duties.titleOf(list.duty_id) }}</strong> duty.
    </p>

    <ul class="item-list">
      <li v-for="item in list.items" :key="item.id" class="item-row">
        <label class="check-toggle">
          <input type="checkbox" :checked="item.is_checked" @change="onToggle(item.id)" />
          <span :class="{ done: item.is_checked }">
            {{ item.name }}
            <span v-if="item.quantity" class="muted">({{ item.quantity }})</span>
          </span>
        </label>
        <button type="button" class="delete-btn" @click="onDeleteItem(item.id)">Delete</button>
      </li>
    </ul>

    <form class="card" @submit.prevent="submit">
      <div class="add-row">
        <input v-model="itemName" placeholder="Item name" required />
        <input v-model="itemQuantity" placeholder="Qty" class="qty-input" />
        <button type="submit" :disabled="loading">Add</button>
      </div>
      <p v-if="error" class="error">{{ error }}</p>
    </form>

    <div class="danger-zone">
      <button type="button" class="danger" @click="onDeleteList">Delete list</button>
    </div>
  </div>
</template>

<script setup lang="ts">
const route = useRoute()
const router = useRouter()
const shopping = useShoppingStore()
const duties = useDutiesStore()

await Promise.all([shopping.fetchList(route.params.id as string), duties.fetchDuties()])

const list = computed(() => shopping.current)

const itemName = ref('')
const itemQuantity = ref('')
const loading = ref(false)
const error = ref('')

async function submit() {
  error.value = ''
  loading.value = true
  try {
    await shopping.addItem(route.params.id as string, itemName.value, itemQuantity.value)
    itemName.value = ''
    itemQuantity.value = ''
  } catch {
    error.value = 'Could not add that item.'
  } finally {
    loading.value = false
  }
}

async function onToggle(itemId: string) {
  await shopping.toggleChecked(itemId)
}

async function onDeleteItem(itemId: string) {
  await shopping.deleteItem(itemId)
}

async function onDeleteList() {
  await shopping.deleteList(route.params.id as string)
  await router.push('/shopping')
}
</script>

<style scoped>
.muted {
  color: var(--muted);
}

.item-list {
  list-style: none;
  padding: 0;
  margin: 1rem 0;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.item-row {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  border: 1px solid var(--border);
  border-radius: 0.6rem;
  padding: 0.7rem;
}

.check-toggle {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  flex: 1;
}

.check-toggle span.done {
  text-decoration: line-through;
  color: var(--muted);
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
  border: 1px solid var(--border);
  border-radius: 0.75rem;
  padding: 1rem;
  margin-bottom: 1.5rem;
}

.add-row {
  display: flex;
  gap: 0.5rem;
}

.add-row input {
  padding: 0.6rem;
  border-radius: 0.5rem;
  border: 1px solid var(--border);
  background: var(--bg);
  color: var(--fg);
  font-size: 1rem;
}

.add-row input:first-child {
  flex: 1;
}

.qty-input {
  width: 4.5rem;
}

.add-row button {
  padding: 0.6rem 1rem;
  border-radius: 0.5rem;
  border: none;
  background: var(--accent);
  color: white;
}

.error {
  color: #dc2626;
  font-size: 0.85rem;
  margin-top: 0.5rem;
}

.danger-zone button.danger {
  padding: 0.55rem 0.9rem;
  border-radius: 0.5rem;
  border: 1px solid #dc2626;
  background: var(--bg);
  color: #dc2626;
}
</style>
