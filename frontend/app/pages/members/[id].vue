<template>
  <div>
    <PageHeader :title="members.nameOf(memberId)" back="/" />

    <div class="profile-card">
      <Avatar
        :user-id="memberId"
        :name="members.nameOf(memberId)"
        :avatar-updated-at="members.avatarUpdatedAtOf(memberId)"
        :size="72"
      />
    </div>

    <h2>Awards</h2>
    <p v-if="!badges.length" class="muted">No awards yet.</p>
    <ul class="badge-list">
      <li v-for="badge in badges" :key="`${badge.kind}-${badge.month}`" class="badge-row">
        <span class="badge-emoji">{{ badge.emoji ?? '🏆' }}</span>
        <div class="badge-text">
          <strong>{{ badge.title }}</strong>
          <span class="muted">{{ formatMonth(badge.month) }}</span>
        </div>
      </li>
    </ul>
  </div>
</template>

<script setup lang="ts">
const route = useRoute()
const members = useMembersStore()
const awards = useAwardsStore()

const memberId = route.params.id as string

await members.ensureLoaded()
const history = await awards.fetchMemberHistory(memberId)
const badges = history.badges

function formatMonth(monthIso: string) {
  return new Date(monthIso).toLocaleDateString(undefined, { month: 'long', year: 'numeric' })
}
</script>

<style scoped>
.muted {
  color: var(--muted);
}

.profile-card {
  display: flex;
  justify-content: center;
  margin: 1rem 0 1.5rem;
}

.badge-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
}

.badge-row {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  border: 1px solid var(--border);
  border-radius: 0.6rem;
  padding: 0.7rem;
}

.badge-emoji {
  font-size: 1.6rem;
  line-height: 1;
}

.badge-text {
  display: flex;
  flex-direction: column;
}

.badge-text span {
  font-size: 0.8rem;
}
</style>
