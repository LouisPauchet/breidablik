export interface DutyAssignee {
  user_id: string
  order_index: number
}

export interface CurrentPeriod {
  period_index: number
  start_date: string
  end_date: string
  assignee_user_id: string
}

export interface Duty {
  id: string
  title: string
  description: string | null
  start_date: string
  task_interval_days: number
  rotation_interval_days: number
  is_active: boolean
  created_by_id: string
  created_at: string
  assignees: DutyAssignee[]
  current_period: CurrentPeriod
}

export interface DutyOccurrence {
  id: string
  due_date: string
  period_index: number
  assigned_user_id: string
  is_manual_override: boolean
  is_done: boolean
  done_by_id: string | null
  done_at: string | null
  assignee_away: boolean
}

export interface DutyOverride {
  id: string
  period_index: number
  assignee_user_id: string
  reason: string | null
  created_by_id: string
  created_at: string
}

export interface DutyDetail extends Duty {
  occurrences: DutyOccurrence[]
  overrides: DutyOverride[]
}

export interface OnDutyToday {
  duty_id: string
  duty_title: string
  assignee_user_id: string
}

export interface DutyCreatePayload {
  title: string
  description?: string | null
  start_date: string
  task_interval_days: number
  rotation_interval_days: number
  assignee_user_ids: string[]
}

export const useDutiesStore = defineStore('duties', {
  state: () => ({
    duties: [] as Duty[],
    onDutyToday: [] as OnDutyToday[],
    current: null as DutyDetail | null,
  }),
  actions: {
    async fetchDuties() {
      this.duties = await $fetch<Duty[]>('/api/duties')
    },

    async fetchOnDutyToday() {
      this.onDutyToday = await $fetch<OnDutyToday[]>('/api/duties/on-duty-today')
    },

    async fetchDuty(id: string) {
      this.current = await $fetch<DutyDetail>(`/api/duties/${id}`)
      return this.current
    },

    async createDuty(payload: DutyCreatePayload) {
      return await $fetch<Duty>('/api/duties', { method: 'POST', body: payload })
    },

    async archiveDuty(id: string) {
      await $fetch(`/api/duties/${id}`, { method: 'PATCH', body: { is_active: false } })
    },

    async deleteDuty(id: string) {
      await $fetch(`/api/duties/${id}`, { method: 'DELETE' })
    },

    async toggleOccurrenceDone(dutyId: string, occurrenceId: string) {
      const updated = await $fetch<DutyOccurrence>(
        `/api/duties/${dutyId}/occurrences/${occurrenceId}/toggle-done`,
        { method: 'POST' }
      )
      this._patchOccurrence(updated)
      return updated
    },

    async reassignOccurrence(dutyId: string, occurrenceId: string, assignedUserId: string) {
      const updated = await $fetch<DutyOccurrence>(`/api/duties/${dutyId}/occurrences/${occurrenceId}`, {
        method: 'PATCH',
        body: { assigned_user_id: assignedUserId },
      })
      this._patchOccurrence(updated)
      return updated
    },

    _patchOccurrence(updated: DutyOccurrence) {
      if (!this.current) return
      const idx = this.current.occurrences.findIndex((o) => o.id === updated.id)
      if (idx !== -1) this.current.occurrences[idx] = updated
    },
  },
})
