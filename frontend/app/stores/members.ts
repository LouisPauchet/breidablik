export interface Member {
  id: string
  display_name: string
}

export const useMembersStore = defineStore('members', {
  state: () => ({
    members: [] as Member[],
    loaded: false,
  }),
  getters: {
    nameOf: (state) => (userId: string) =>
      state.members.find((m) => m.id === userId)?.display_name ?? 'Unknown',
  },
  actions: {
    async ensureLoaded() {
      if (this.loaded) return
      await this.fetch()
    },
    async fetch() {
      this.members = await $fetch<Member[]>('/api/members')
      this.loaded = true
    },
  },
})
