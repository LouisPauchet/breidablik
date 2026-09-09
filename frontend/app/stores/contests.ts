export interface ContestTallyEntry {
  user_id: string
  count: number
}

export interface ContestDuty {
  id: string
  title: string
  description: string | null
  icon: string
  is_active: boolean
  created_by_id: string
  created_at: string
}

export interface ContestSummaryEntry extends ContestDuty {
  tally: ContestTallyEntry[]
}

export interface ContestDutyCreatePayload {
  title: string
  description?: string | null
  icon: string
}

export const useContestsStore = defineStore('contests', {
  state: () => ({
    contests: [] as ContestSummaryEntry[],
  }),
  actions: {
    async fetchContests() {
      this.contests = await $fetch<ContestSummaryEntry[]>('/api/contests')
      return this.contests
    },

    async createContest(payload: ContestDutyCreatePayload) {
      const created = await $fetch<ContestDuty>('/api/contests', { method: 'POST', body: payload })
      await this.fetchContests()
      return created
    },

    async logCompletion(contestId: string) {
      await $fetch(`/api/contests/${contestId}/log`, { method: 'POST' })
      await this.fetchContests()
    },
  },
})
