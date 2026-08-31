export interface DutyTeamMember {
  user_id: string
  order_index: number
}

export interface DutyTeamDutySummary {
  id: string
  title: string
  is_active: boolean
}

export interface TeamPeriod {
  period_index: number
  start_date: string
  end_date: string
}

export interface TeamAssignment {
  duty_id: string
  duty_title: string
  assignee_user_id: string
}

export interface DutyTeam {
  id: string
  name: string
  description: string | null
  start_date: string
  rotation_interval_days: number
  created_by_id: string
  created_at: string
  members: DutyTeamMember[]
  duties: DutyTeamDutySummary[]
  current_period: TeamPeriod
  current_assignments: TeamAssignment[]
}

export interface DutyTeamCreatePayload {
  name: string
  description?: string | null
  start_date: string
  rotation_interval_days: number
  member_user_ids: string[]
}

export const useDutyTeamsStore = defineStore('dutyTeams', {
  state: () => ({
    teams: [] as DutyTeam[],
    current: null as DutyTeam | null,
  }),
  getters: {
    nameOf: (state) => (teamId: string) => state.teams.find((t) => t.id === teamId)?.name ?? 'Unknown team',
  },
  actions: {
    async fetchTeams() {
      this.teams = await $fetch<DutyTeam[]>('/api/duty-teams')
    },

    async fetchTeam(id: string) {
      this.current = await $fetch<DutyTeam>(`/api/duty-teams/${id}`)
      return this.current
    },

    async createTeam(payload: DutyTeamCreatePayload) {
      const created = await $fetch<DutyTeam>('/api/duty-teams', { method: 'POST', body: payload })
      this.teams.push(created)
      return created
    },

    async updateMembers(id: string, memberUserIds: string[]) {
      this.current = await $fetch<DutyTeam>(`/api/duty-teams/${id}`, {
        method: 'PATCH',
        body: { member_user_ids: memberUserIds },
      })
      return this.current
    },

    async deleteTeam(id: string) {
      await $fetch(`/api/duty-teams/${id}`, { method: 'DELETE' })
      this.teams = this.teams.filter((t) => t.id !== id)
    },
  },
})
