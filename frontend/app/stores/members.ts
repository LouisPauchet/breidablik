export interface Member {
  id: string
  display_name: string
  birthday: string | null
  avatar_updated_at: string | null
}

export const useMembersStore = defineStore('members', {
  state: () => ({
    members: [] as Member[],
    loaded: false,
  }),
  getters: {
    nameOf: (state) => (userId: string) =>
      state.members.find((m) => m.id === userId)?.display_name ?? 'Unknown',
    avatarUpdatedAtOf: (state) => (userId: string) =>
      state.members.find((m) => m.id === userId)?.avatar_updated_at ?? null,
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
