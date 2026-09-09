<template>
  <div>
    <PageHeader title="Contest duties">
      <NuxtLink to="/contests/new" class="btn-primary">+ New</NuxtLink>
    </PageHeader>

    <p v-if="!contests.contests.length" class="muted">
      No contest duties yet. Create one for an open chore anyone can pitch in on — no
      schedule, no assignee, just log it whenever you do it.
    </p>

    <p v-else class="muted small">
      Only your own count is shown — who's ahead stays secret until the month's award.
    </p>

    <div class="contest-list">
      <ContestLogCard v-for="contest in contests.contests" :key="contest.id" :contest="contest" />
    </div>
  </div>
</template>

<script setup lang="ts">
const contests = useContestsStore()

await contests.fetchContests()
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

.contest-list {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  margin-top: 0.75rem;
}
</style>
