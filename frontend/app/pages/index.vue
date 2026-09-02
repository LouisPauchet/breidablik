<template>
  <div>
    <PageHeader :title="`Hi ${authStore.user?.display_name}`" />

    <blockquote v-if="quote" class="quote">
      <p>&ldquo;{{ quote.text }}&rdquo;</p>
      <cite>&mdash; {{ quote.author }}</cite>
    </blockquote>

    <h2>Your duties</h2>
    <p v-if="!myDuties.length" class="muted">Nothing on your plate right now.</p>
    <ul class="widget-list highlight">
      <li v-for="entry in myDuties" :key="entry.duty_id">
        <NuxtLink :to="`/duties/${entry.duty_id}`">
          <strong>{{ entry.duty_title }}</strong>
        </NuxtLink>
      </li>
    </ul>

    <h2>Household duties</h2>
    <p v-if="!duties.onDutyToday.length" class="muted">No active duties yet.</p>
    <ul class="widget-list">
      <li v-for="entry in duties.onDutyToday" :key="entry.duty_id" class="duty-row">
        <NuxtLink :to="`/members/${entry.assignee_user_id}`" class="avatar-link">
          <Avatar
            :user-id="entry.assignee_user_id"
            :name="members.nameOf(entry.assignee_user_id)"
            :avatar-updated-at="members.avatarUpdatedAtOf(entry.assignee_user_id)"
            :size="28"
          />
        </NuxtLink>
        <NuxtLink :to="`/duties/${entry.duty_id}`" class="duty-text-link">
          <strong>{{ entry.duty_title }}</strong> — {{ members.nameOf(entry.assignee_user_id) }}
        </NuxtLink>
      </li>
    </ul>

    <template v-if="current?.phase === 'suggesting' && !current.my_suggestion_submitted">
      <h2>Suggest this month's award</h2>
      <form class="card" @submit.prevent="onSuggest">
        <div class="suggest-row">
          <input v-model="suggestTitle" placeholder="Award title, e.g. Best Cook" maxlength="100" required />
          <input v-model="suggestEmoji" placeholder="🍳" maxlength="8" required class="emoji-input" />
        </div>
        <p v-if="suggestError" class="error">{{ suggestError }}</p>
        <button type="submit" class="submit-btn" :disabled="suggestLoading">Suggest</button>
      </form>
    </template>

    <template v-if="current?.phase === 'voting' && current.drawn_category_title">
      <h2>{{ current.drawn_category_emoji }} {{ current.drawn_category_title }}</h2>
      <p class="muted">
        {{ current.my_vote_candidate_id ? 'You voted — you can still change it.' : 'Vote for who should win:' }}
      </p>
      <ul class="vote-list">
        <li v-for="m in members.members" :key="m.id">
          <button
            type="button"
            class="vote-row"
            :class="{ selected: current.my_vote_candidate_id === m.id }"
            @click="onVote(m.id)"
          >
            <Avatar :user-id="m.id" :name="m.display_name" :avatar-updated-at="m.avatar_updated_at" :size="28" />
            <span>{{ m.display_name }}</span>
          </button>
        </li>
      </ul>
      <button
        v-if="authStore.user?.is_superuser"
        type="button"
        class="link-btn"
        @click="onVeto(current.id)"
      >
        Veto this award
      </button>
    </template>

    <template v-if="latestDecided">
      <h2>This month's awards</h2>
      <div class="card">
        <div v-if="latestDecided.duty_master_winner_id" class="winner-row">
          <NuxtLink :to="`/members/${latestDecided.duty_master_winner_id}`" class="avatar-link">
            <Avatar
              :user-id="latestDecided.duty_master_winner_id"
              :name="members.nameOf(latestDecided.duty_master_winner_id)"
              :avatar-updated-at="members.avatarUpdatedAtOf(latestDecided.duty_master_winner_id)"
              :badge="DUTY_MASTER_BADGE_EMOJI"
              :size="40"
            />
          </NuxtLink>
          <span
            ><strong>{{ DUTY_MASTER_BADGE_EMOJI }} Duty Master</strong> —
            {{ members.nameOf(latestDecided.duty_master_winner_id) }}</span
          >
        </div>
        <p v-else class="muted">No Duty Master this month.</p>

        <div v-if="latestDecided.community_award_vetoed" class="winner-row">
          <span class="muted">{{ latestDecided.drawn_category_emoji }} {{ latestDecided.drawn_category_title }} — vetoed by an admin.</span>
        </div>
        <div v-else-if="latestDecided.community_award_winner_id" class="winner-row">
          <NuxtLink :to="`/members/${latestDecided.community_award_winner_id}`" class="avatar-link">
            <Avatar
              :user-id="latestDecided.community_award_winner_id"
              :name="members.nameOf(latestDecided.community_award_winner_id)"
              :avatar-updated-at="members.avatarUpdatedAtOf(latestDecided.community_award_winner_id)"
              :badge="latestDecided.drawn_category_emoji"
              :size="40"
            />
          </NuxtLink>
          <span
            ><strong>{{ latestDecided.drawn_category_emoji }} {{ latestDecided.drawn_category_title }}</strong> —
            {{ members.nameOf(latestDecided.community_award_winner_id) }}</span
          >
        </div>
        <p v-else class="muted">No community award this month.</p>

        <button
          v-if="authStore.user?.is_superuser && latestDecided.drawn_category_title && !latestDecided.community_award_vetoed"
          type="button"
          class="link-btn"
          @click="onVeto(latestDecided.id)"
        >
          Veto this award
        </button>
      </div>
    </template>

    <button @click="handleLogout">Log out</button>
  </div>
</template>

<script setup lang="ts">
interface Quote {
  text: string
  author: string
}

const authStore = useAuthStore()
const duties = useDutiesStore()
const members = useMembersStore()
const awards = useAwardsStore()
const router = useRouter()

const quote = ref<Quote | null>(null)

await Promise.all([
  members.ensureLoaded(),
  duties.fetchOnDutyToday(),
  awards.fetchSummary(),
  $fetch<Quote>('/api/quote-of-the-day')
    .then((res) => (quote.value = res))
    .catch(() => {}),
])

const myDuties = computed(() =>
  duties.onDutyToday.filter((entry) => entry.assignee_user_id === authStore.user?.id)
)

const current = computed(() => awards.summary?.current ?? null)
const latestDecided = computed(() => awards.summary?.latest_decided ?? null)

const suggestTitle = ref('')
const suggestEmoji = ref('')
const suggestLoading = ref(false)
const suggestError = ref('')

async function onSuggest() {
  suggestError.value = ''
  suggestLoading.value = true
  try {
    await awards.suggest(suggestTitle.value, suggestEmoji.value)
    suggestTitle.value = ''
    suggestEmoji.value = ''
  } catch {
    suggestError.value = 'Could not submit your suggestion — try again.'
  } finally {
    suggestLoading.value = false
  }
}

async function onVote(candidateUserId: string) {
  if (!current.value) return
  await awards.vote(current.value.id, candidateUserId)
}

async function onVeto(cycleId: string) {
  await awards.veto(cycleId)
}

async function handleLogout() {
  await authStore.logout()
  await router.push('/login')
}
</script>

<style scoped>
.muted {
  color: var(--muted);
}

.quote {
  margin: 0 0 1.5rem;
  padding: 1rem 1.1rem;
  border-left: 3px solid var(--accent);
  font-style: italic;
}

.quote p {
  margin: 0;
}

.quote cite {
  display: block;
  margin-top: 0.4rem;
  font-style: normal;
  font-size: 0.85rem;
  color: var(--muted);
}

.widget-list {
  list-style: none;
  padding: 0;
  margin: 0 0 1.5rem;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.widget-list a {
  display: block;
  border: 1px solid var(--border);
  border-radius: 0.6rem;
  padding: 0.7rem;
  color: var(--fg);
  text-decoration: none;
}

.widget-list.highlight a {
  background: color-mix(in srgb, var(--accent) 12%, transparent);
  border-color: var(--accent);
}

.widget-list li.duty-row {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  border: 1px solid var(--border);
  border-radius: 0.6rem;
  padding: 0.7rem;
}

/* The avatar and the duty text are separate links (to a member's award history and to the
   duty respectively) — overriding the generic `.widget-list a` card styling above, since
   `.duty-row` now carries that border/padding itself. */
.widget-list a.avatar-link,
.widget-list a.duty-text-link {
  display: inline-flex;
  border: none;
  padding: 0;
  border-radius: 0;
}

.widget-list a.duty-text-link {
  flex: 1;
  min-width: 0;
  align-items: center;
}

.card {
  border: 1px solid var(--border);
  border-radius: 0.75rem;
  padding: 1rem;
  margin-bottom: 1.5rem;
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
}

.suggest-row {
  display: flex;
  gap: 0.5rem;
}

.suggest-row input {
  padding: 0.6rem;
  border-radius: 0.5rem;
  border: 1px solid var(--border);
  background: var(--bg);
  color: var(--fg);
  font-size: 1rem;
}

.suggest-row input:not(.emoji-input) {
  flex: 1;
  min-width: 0;
}

.emoji-input {
  width: 3.5rem;
  text-align: center;
}

.submit-btn {
  align-self: flex-start;
  padding: 0.55rem 1rem;
  border-radius: 0.5rem;
  border: none;
  background: var(--accent);
  color: white;
  font-size: 0.95rem;
}

.error {
  color: #dc2626;
  font-size: 0.85rem;
}

.vote-list {
  list-style: none;
  padding: 0;
  margin: 0 0 0.5rem;
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.vote-row {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  width: 100%;
  padding: 0.5rem 0.6rem;
  border: 1px solid var(--border);
  border-radius: 0.6rem;
  background: var(--bg);
  color: var(--fg);
  font-size: 0.95rem;
  text-align: left;
}

.vote-row.selected {
  border-color: var(--accent);
  background: color-mix(in srgb, var(--accent) 12%, transparent);
}

.winner-row {
  display: flex;
  align-items: center;
  gap: 0.7rem;
}

.link-btn {
  align-self: flex-start;
  background: none;
  border: none;
  color: var(--link);
  padding: 0;
  font-size: 0.85rem;
}

button {
  padding: 0.6rem 1rem;
  border-radius: 0.5rem;
  border: 1px solid var(--border);
  background: var(--bg);
  color: var(--fg);
}
</style>
