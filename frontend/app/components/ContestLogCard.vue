<template>
  <div class="contest-card">
    <div class="contest-header">
      <span class="contest-icon">{{ contest.icon }}</span>
      <div class="contest-title">
        <strong>{{ contest.title }}</strong>
        <p v-if="contest.description" class="muted small">{{ contest.description }}</p>
      </div>
      <span class="my-count" :title="'How many times you logged this, this month'">
        {{ contest.my_count }}<span class="muted small"> you</span>
      </span>
    </div>

    <button type="button" class="log-btn" :disabled="loading || !!cooldownLabel" @click="onLog">
      {{ cooldownLabel ? `Done — again ${cooldownLabel}` : 'I did this' }}
    </button>
    <p v-if="error" class="error">{{ error }}</p>
  </div>
</template>

<script setup lang="ts">
const props = defineProps<{
  contest: {
    id: string
    title: string
    description: string | null
    icon: string
    my_count: number
    next_log_allowed_at: string | null
  }
}>()

const contests = useContestsStore()

const loading = ref(false)
const error = ref('')

// The cooldown label has to re-evaluate on its own, otherwise the button would stay disabled
// until a manual reload even after the interval has actually elapsed.
const now = ref(Date.now())
let ticker: ReturnType<typeof setInterval> | undefined
onMounted(() => {
  ticker = setInterval(() => (now.value = Date.now()), 30_000)
})
onUnmounted(() => {
  if (ticker) clearInterval(ticker)
})

const cooldownLabel = computed(() => {
  if (!props.contest.next_log_allowed_at) return ''
  const readyAt = new Date(props.contest.next_log_allowed_at).getTime()
  const remainingMinutes = Math.ceil((readyAt - now.value) / 60_000)
  if (remainingMinutes <= 0) return ''
  if (remainingMinutes < 60) return `in ${remainingMinutes} min`
  const hours = Math.floor(remainingMinutes / 60)
  const minutes = remainingMinutes % 60
  if (hours < 24) return minutes ? `in ${hours}h ${minutes}m` : `in ${hours}h`
  return `in ${Math.floor(hours / 24)}d`
})

async function onLog() {
  error.value = ''
  loading.value = true
  try {
    await contests.logCompletion(props.contest.id)
  } catch {
    // The store refreshes regardless, so the button will already reflect the real cooldown.
    error.value = 'Someone just logged this — it can be logged again once the wait is over.'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.contest-card {
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
  border: 1px solid var(--border);
  border-radius: 0.75rem;
  padding: 1rem;
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

.contest-title {
  flex: 1;
  min-width: 0;
}

.contest-title p {
  margin: 0.15rem 0 0;
}

.my-count {
  flex-shrink: 0;
  font-weight: 600;
  font-size: 1.1rem;
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

.log-btn:disabled {
  background: var(--border);
  color: var(--muted);
}

.muted {
  color: var(--muted);
}

.small {
  font-size: 0.8rem;
}

.error {
  color: #dc2626;
  font-size: 0.85rem;
  margin: 0;
}
</style>
