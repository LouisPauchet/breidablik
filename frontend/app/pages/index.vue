<template>
  <div>
    <h1>Hi {{ authStore.user?.display_name }}</h1>
    <p class="muted">Home dashboard — who's on duty, upcoming events, and open tasks land here.</p>
    <button @click="handleLogout">Log out</button>
  </div>
</template>

<script setup lang="ts">
const authStore = useAuthStore()
const router = useRouter()

async function handleLogout() {
  await authStore.logout()
  await router.push('/login')
}
</script>

<style scoped>
.muted {
  color: var(--muted);
}

button {
  padding: 0.6rem 1rem;
  border-radius: 0.5rem;
  border: 1px solid var(--border);
  background: var(--bg);
  color: var(--fg);
}
</style>
