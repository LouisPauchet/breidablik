export interface ContestDuty {
  id: string
  title: string
  description: string | null
  icon: string
  min_interval_minutes: number
  show_on_home: boolean
  is_active: boolean
  created_by_id: string
  created_at: string
}

export interface ContestSummaryEntry extends ContestDuty {
  // Deliberately only ever your own count — see app/services/contests.py:get_my_month_counts.
  my_count: number
  next_log_allowed_at: string | null
}

export interface ContestDutyCreatePayload {
  title: string
  description?: string | null
  icon: string
  min_interval_minutes?: number
  show_on_home?: boolean
}

export const useContestsStore = defineStore('contests', {
  state: () => ({
    contests: [] as ContestSummaryEntry[],
    homeContests: [] as ContestSummaryEntry[],
  }),
  actions: {
    async fetchContests() {
      this.contests = await $fetch<ContestSummaryEntry[]>('/api/contests')
      return this.contests
    },

    async fetchHomeContests() {
      this.homeContests = await $fetch<ContestSummaryEntry[]>('/api/contests', {
        query: { home_only: true },
      })
      return this.homeContests
    },

    async createContest(payload: ContestDutyCreatePayload) {
      const created = await $fetch<ContestDuty>('/api/contests', { method: 'POST', body: payload })
      await this.fetchContests()
      return created
    },

    async logCompletion(contestId: string) {
      try {
        await $fetch(`/api/contests/${contestId}/log`, { method: 'POST' })
      } finally {
        // Refresh even when the log was rejected (e.g. the cooldown hadn't elapsed), so the
        // UI picks up the server's authoritative next_log_allowed_at either way.
        await Promise.all([
          this.contests.length ? this.fetchContests() : Promise.resolve(),
          this.homeContests.length ? this.fetchHomeContests() : Promise.resolve(),
        ])
      }
    },
  },
})
