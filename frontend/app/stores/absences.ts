export interface Absence {
  id: string
  user_id: string
  start_date: string
  end_date: string
  reason: string | null
  auto_reassign: boolean
  created_at: string
}

export interface AbsenceCreatePayload {
  start_date: string
  end_date: string
  reason?: string | null
  auto_reassign?: boolean
}

export const useAbsencesStore = defineStore('absences', {
  state: () => ({
    absences: [] as Absence[],
  }),
  actions: {
    async fetchAbsences() {
      this.absences = await $fetch<Absence[]>('/api/absences')
    },

    async createAbsence(payload: AbsenceCreatePayload) {
      const created = await $fetch<Absence>('/api/absences', { method: 'POST', body: payload })
      this.absences.push(created)
      this.absences.sort((a, b) => a.start_date.localeCompare(b.start_date))
      return created
    },

    async deleteAbsence(id: string) {
      await $fetch(`/api/absences/${id}`, { method: 'DELETE' })
      this.absences = this.absences.filter((a) => a.id !== id)
    },
  },
})
