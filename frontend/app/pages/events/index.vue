<template>
  <div>
    <header class="page-header">
      <h1>Events</h1>
      <NuxtLink to="/events/new" class="btn-primary">+ New</NuxtLink>
    </header>

    <p v-if="!events.events.length" class="muted">No events yet.</p>
    <ul class="event-list">
      <li v-for="event in events.events" :key="event.id">
        <NuxtLink :to="`/events/${event.id}`" class="event-card">
          <div class="event-title">
            {{ event.title }}
            <span class="type-badge">{{ event.event_type }}</span>
          </div>
          <div class="event-meta">
            {{ formatDateTime(event.start_at) }}
            <span v-if="event.location"> &middot; {{ event.location }}</span>
          </div>
        </NuxtLink>
      </li>
    </ul>
  </div>
</template>

<script setup lang="ts">
const events = useEventsStore()
await events.fetchEvents()

function formatDateTime(iso: string) {
  return new Date(iso).toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  })
}
</script>

<style scoped>
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
}

.btn-primary {
  background: var(--accent);
  color: white;
  padding: 0.5rem 0.9rem;
  border-radius: 0.5rem;
  text-decoration: none;
  font-size: 0.9rem;
}

.muted {
  color: var(--muted);
}

.event-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
}

.event-card {
  display: block;
  border: 1px solid var(--border);
  border-radius: 0.75rem;
  padding: 0.9rem;
  text-decoration: none;
  color: var(--fg);
}

.event-title {
  font-weight: 600;
  margin-bottom: 0.25rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.type-badge {
  font-size: 0.7rem;
  font-weight: 400;
  color: var(--muted);
  border: 1px solid var(--border);
  border-radius: 999px;
  padding: 0.1rem 0.5rem;
  text-transform: capitalize;
}

.event-meta {
  font-size: 0.85rem;
  color: var(--muted);
}
</style>
