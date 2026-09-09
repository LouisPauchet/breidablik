<template>
  <div>
    <PageHeader title="Contest duties">
      <NuxtLink to="/contests/new" class="btn-primary">+ New</NuxtLink>
    </PageHeader>

    <p v-if="!contests.contests.length" class="muted">
      No contest duties yet. Create one for an open chore anyone can pitch in on — no
      schedule, no assignee, just log it whenever you do it.
    </p>

    <div v-for="contest in contests.contests" :key="contest.id" class="card contest-card">
      <div class="contest-header">
        <span class="contest-icon">{{ contest.icon }}</span>
        <div class="contest-title">
          <strong>{{ contest.title }}</strong>
          <p v-if="contest.description" class="muted small">{{ contest.description }}</p>
        </div>
      </div>

      <button
        type="button"
        class="log-btn"
        :disabled="loggingId === contest.id"
        @click="onLog(contest.id)"
      >
        I did this
      </button>

      <p class="muted small">This month:</p>
      <ul v-if="contest.tally.length" class="tally-list">
        <li
          v-for="row in contest.tally"
          :key="row.user_id"
          class="tally-row"
          :class="{ me: row.user_id === authStore.user?.id }"
        >
          <Avatar
            :user-id="row.user_id"
            :name="members.nameOf(row.user_id)"
            :avatar-updated-at="members.avatarUpdatedAtOf(row.user_id)"
            :size="24"
          />
          <span>{{ members.nameOf(row.user_id) }}</span>
          <strong>{{ row.count }}</strong>
        </li>
      </ul>
      <p v-else class="muted small">Nobody's logged this yet this month.</p>
    </div>
  </div>
</template>

<script setup lang="ts">
const contests = useContestsStore()
const members = useMembersStore()
const authStore = useAuthStore()

await Promise.all([members.ensureLoaded(), contests.fetchContests()])

const loggingId = ref<string | null>(null)

async function onLog(contestId: string) {
  loggingId.value = contestId
  try {
    await contests.logCompletion(contestId)
  } finally {
    loggingId.value = null
  }
}
</script>

<style scoped>
.btn-primary {
  background: var(--accent);
  color: white;
  padding: 0.5rem 0.9rem;
  border-radius: 0.5rem;
  text-decoration: none;
  font-size: 0.85rem;
  white-space: nowrap;
}

.muted {
  color: var(--muted);
}

.small {
  font-size: 0.8rem;
}

.card {
  border: 1px solid var(--border);
  border-radius: 0.75rem;
  padding: 1rem;
  margin-bottom: 1rem;
}

.contest-card {
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
}

.contest-header {
  display: flex;
  align-items: center;
  gap: 0.7rem;
}

.contest-icon {
  font-size: 1.8rem;
  line-height: 1;
}

.contest-title p {
  margin: 0.15rem 0 0;
}

.log-btn {
  align-self: flex-start;
  padding: 0.55rem 1rem;
  border-radius: 0.5rem;
  border: none;
  background: var(--accent);
  color: white;
  font-size: 0.95rem;
}

.tally-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.tally-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.9rem;
  padding: 0.3rem 0.4rem;
  border-radius: 0.4rem;
}

.tally-row.me {
  background: color-mix(in srgb, var(--accent) 12%, transparent);
}

.tally-row span {
  flex: 1;
}
</style>
