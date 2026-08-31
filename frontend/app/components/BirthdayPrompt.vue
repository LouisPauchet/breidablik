<template>
  <div v-if="show" class="overlay">
    <div class="modal">
      <h2>When's your birthday?</h2>
      <p class="muted">
        So the household can see birthdays coming up on the calendar.
      </p>
      <label>
        Birthday
        <input v-model="birthday" type="date" required :max="todayIso" />
      </label>
      <p v-if="error" class="error">{{ error }}</p>
      <div class="btn-row">
        <button type="button" class="primary" :disabled="!birthday || loading" @click="onSave">Save</button>
        <button v-if="authStore.user?.is_superuser" type="button" class="secondary" @click="dismissed = true">
          Skip for now
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
// Deliberately no backdrop-click or Escape-key dismissal — a non-admin can only get past
// this by saving a birthday. Only admins get the "Skip for now" button at all.
const authStore = useAuthStore()

const birthday = ref('')
const loading = ref(false)
const error = ref('')
const dismissed = ref(false)
const todayIso = new Date().toISOString().slice(0, 10)

const show = computed(() => !!authStore.user && !authStore.user.birthday && !dismissed.value)

async function onSave() {
  error.value = ''
  loading.value = true
  try {
    await authStore.setBirthday(birthday.value)
  } catch {
    error.value = 'Could not save that date — try again.'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.overlay {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1rem;
  z-index: 1000;
}

.modal {
  background: var(--bg);
  color: var(--fg);
  border-radius: 0.75rem;
  padding: 1.5rem;
  max-width: 360px;
  width: 100%;
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.3);
}

.modal h2 {
  margin-top: 0;
}

.muted {
  color: var(--muted);
  font-size: 0.9rem;
}

label {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  font-size: 0.9rem;
  margin: 1rem 0;
}

input {
  padding: 0.6rem;
  border-radius: 0.5rem;
  border: 1px solid var(--border);
  background: var(--bg);
  color: var(--fg);
  font-size: 1rem;
}

.error {
  color: #dc2626;
  font-size: 0.85rem;
}

.btn-row {
  display: flex;
  gap: 0.5rem;
}

.btn-row button {
  flex: 1;
  padding: 0.6rem;
  border-radius: 0.5rem;
  font-size: 0.95rem;
}

.btn-row .primary {
  border: none;
  background: var(--accent);
  color: white;
}

.btn-row .secondary {
  border: 1px solid var(--border);
  background: var(--bg);
  color: var(--fg);
}
</style>
