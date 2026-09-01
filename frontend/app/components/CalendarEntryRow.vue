<template>
  <li class="agenda-row">
    <span class="kind-badge" :class="entry.kind">{{ entry.kind }}</span>
    <div class="agenda-body">
      <NuxtLink v-if="entry.href" :to="entry.href" class="agenda-title" :class="{ done: entry.done }">
        {{ entry.title }}
      </NuxtLink>
      <button
        v-else-if="entry.kind === 'away' && entry.editable"
        type="button"
        class="agenda-title as-button"
        @click="$emit('edit-absence', entry.absenceId!)"
      >
        {{ entry.title }}
      </button>
      <span v-else class="agenda-title" :class="{ done: entry.done }">{{ entry.title }}</span>
      <div class="agenda-meta">{{ entry.whenLabel }}<span v-if="entry.detail"> &middot; {{ entry.detail }}</span></div>
    </div>
  </li>
</template>

<script setup lang="ts">
defineProps<{
  entry: {
    key: string
    kind: 'duty' | 'task' | 'event' | 'away' | 'birthday'
    title: string
    detail: string
    whenLabel: string
    done?: boolean
    href?: string
    editable?: boolean
    absenceId?: string
  }
}>()

defineEmits<{ 'edit-absence': [absenceId: string] }>()
</script>

<style scoped>
.agenda-row {
  display: flex;
  align-items: flex-start;
  gap: 0.6rem;
  border: 1px solid var(--border);
  border-radius: 0.6rem;
  padding: 0.7rem;
}

.kind-badge {
  flex-shrink: 0;
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 0.02em;
  padding: 0.2rem 0.5rem;
  border-radius: 999px;
  color: white;
  margin-top: 0.1rem;
}

.kind-badge.duty {
  background: #0f766e;
}

.kind-badge.task {
  background: #2563eb;
}

.kind-badge.event {
  background: #9333ea;
}

.kind-badge.away {
  background: #d97706;
}

.kind-badge.birthday {
  background: #db2777;
}

.agenda-body {
  flex: 1;
  min-width: 0;
}

.agenda-title {
  display: block;
  font-weight: 600;
  color: var(--fg);
  text-decoration: none;
}

.agenda-title.as-button {
  border: none;
  background: none;
  padding: 0;
  text-align: left;
  font-family: inherit;
  font-size: inherit;
  cursor: pointer;
}

.agenda-title.done {
  text-decoration: line-through;
  color: var(--muted);
  font-weight: 400;
}

.agenda-meta {
  font-size: 0.8rem;
  color: var(--muted);
}
</style>
