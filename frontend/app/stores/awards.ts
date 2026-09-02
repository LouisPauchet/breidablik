export type AwardCyclePhase = 'suggesting' | 'voting' | 'decided'

export interface AwardVoteTally {
  candidate_user_id: string
  vote_count: number
}

export interface AwardCycle {
  id: string
  month: string
  phase: AwardCyclePhase
  drawn_category_title: string | null
  drawn_category_emoji: string | null
  drawn_category_suggested_by_id: string | null
  duty_master_winner_id: string | null
  duty_master_win_count: number | null
  community_award_winner_id: string | null
  community_award_vote_count: number | null
  community_award_vetoed: boolean
  finalized_at: string | null
}

export interface AwardCurrentState extends AwardCycle {
  my_suggestion_submitted: boolean
  my_vote_candidate_id: string | null
  votes: AwardVoteTally[]
}

export interface AwardSummary {
  current: AwardCurrentState | null
  latest_decided: AwardCycle | null
}

export interface MemberAwardBadge {
  month: string
  kind: 'duty_master' | 'community'
  title: string | null
  emoji: string | null
}

export interface MemberAwardHistory {
  user_id: string
  badges: MemberAwardBadge[]
}

export const useAwardsStore = defineStore('awards', {
  state: () => ({
    summary: null as AwardSummary | null,
  }),
  actions: {
    async fetchSummary() {
      this.summary = await $fetch<AwardSummary>('/api/awards/summary')
      return this.summary
    },

    async suggest(title: string, emoji: string) {
      await $fetch('/api/awards/suggestions', { method: 'POST', body: { title, emoji } })
      await this.fetchSummary()
    },

    async vote(cycleId: string, candidateUserId: string) {
      await $fetch(`/api/awards/cycles/${cycleId}/vote`, {
        method: 'PUT',
        body: { candidate_user_id: candidateUserId },
      })
      await this.fetchSummary()
    },

    async veto(cycleId: string, reason?: string) {
      await $fetch(`/api/awards/cycles/${cycleId}/veto`, { method: 'POST', body: { reason: reason ?? null } })
      await this.fetchSummary()
    },

    async fetchMemberHistory(userId: string) {
      return await $fetch<MemberAwardHistory>(`/api/awards/members/${userId}/history`)
    },
  },
})
