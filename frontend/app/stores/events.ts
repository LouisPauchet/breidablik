export type RSVPStatus = 'yes' | 'no' | 'maybe'
export type EventType = 'dinner' | 'party' | 'meeting' | 'other'

export interface EventRSVP {
  user_id: string
  status: RSVPStatus
  responded_at: string
}

export interface EventItem {
  id: string
  title: string
  event_type: EventType
  description: string | null
  location: string | null
  start_at: string
  end_at: string | null
  series_id: string | null
  created_by_id: string
  created_at: string
  rsvps: EventRSVP[]
}

export interface EventSeries {
  id: string
  name: string
  description: string | null
  created_by_id: string
  created_at: string
}

export interface EventCreatePayload {
  title: string
  event_type?: EventType
  description?: string | null
  location?: string | null
  start_at: string
  end_at?: string | null
  series_id?: string | null
}

export interface EventUpdatePayload {
  title?: string
  event_type?: EventType
  description?: string | null
  location?: string | null
  start_at?: string
  end_at?: string | null
  series_id?: string | null
}

export const useEventsStore = defineStore('events', {
  state: () => ({
    events: [] as EventItem[],
    series: [] as EventSeries[],
    current: null as EventItem | null,
  }),
  actions: {
    async fetchEvents(seriesId?: string) {
      this.events = await $fetch<EventItem[]>('/api/events', {
        query: seriesId ? { series_id: seriesId } : undefined,
      })
      return this.events
    },

    async fetchSeries() {
      this.series = await $fetch<EventSeries[]>('/api/events/series')
    },

    async fetchEvent(id: string) {
      this.current = await $fetch<EventItem>(`/api/events/${id}`)
      return this.current
    },

    async createEvent(payload: EventCreatePayload) {
      return await $fetch<EventItem>('/api/events', { method: 'POST', body: payload })
    },

    async updateEvent(id: string, payload: EventUpdatePayload) {
      const updated = await $fetch<EventItem>(`/api/events/${id}`, { method: 'PATCH', body: payload })
      this.current = updated
      const idx = this.events.findIndex((e) => e.id === id)
      if (idx !== -1) this.events[idx] = updated
      return updated
    },

    async createSeries(name: string, description?: string | null) {
      const created = await $fetch<EventSeries>('/api/events/series', {
        method: 'POST',
        body: { name, description },
      })
      this.series.push(created)
      return created
    },

    async deleteEvent(id: string) {
      await $fetch(`/api/events/${id}`, { method: 'DELETE' })
      this.events = this.events.filter((e) => e.id !== id)
    },

    async rsvp(eventId: string, status: RSVPStatus) {
      const updated = await $fetch<EventItem>(`/api/events/${eventId}/rsvp`, {
        method: 'PUT',
        body: { status },
      })
      this.current = updated
      const idx = this.events.findIndex((e) => e.id === eventId)
      if (idx !== -1) this.events[idx] = updated
      return updated
    },
  },
})
