export interface AuthUser {
  id: string
  email: string
  display_name: string
  is_2fa_enabled: boolean
  is_superuser: boolean
  calendar_feed_token: string
  birthday: string | null
  avatar_updated_at: string | null
}

interface LoginResult {
  requires_2fa?: boolean
  user?: AuthUser
}

export const useAuthStore = defineStore('auth', {
  state: () => ({
    user: null as AuthUser | null,
    initialized: false,
  }),
  actions: {
    async fetchMe() {
      try {
        this.user = await $fetch<AuthUser>('/api/auth/me')
      } catch {
        this.user = null
      } finally {
        this.initialized = true
      }
    },

    async login(email: string, password: string) {
      return await $fetch<LoginResult>('/api/auth/login', {
        method: 'POST',
        body: { email, password },
      })
    },

    async verify2fa(code: string) {
      const res = await $fetch<{ user: AuthUser }>('/api/auth/login/2fa', {
        method: 'POST',
        body: { code },
      })
      this.user = res.user
    },

    async loginPin(pin: string) {
      const res = await $fetch<{ user: AuthUser }>('/api/auth/login/pin', {
        method: 'POST',
        body: { pin },
      })
      this.user = res.user
    },

    async regenerateCalendarFeedToken() {
      this.user = await $fetch<AuthUser>('/api/auth/calendar-feed/regenerate', { method: 'POST' })
    },

    async setBirthday(birthday: string) {
      const updated = await $fetch<{ birthday: string | null }>('/api/users/me', {
        method: 'PATCH',
        body: { birthday },
      })
      if (this.user) this.user.birthday = updated.birthday
    },

    async uploadAvatar(file: File) {
      const form = new FormData()
      form.append('file', file)
      const res = await $fetch<{ avatar_updated_at: string }>('/api/users/me/avatar', {
        method: 'POST',
        body: form,
      })
      if (this.user) this.user.avatar_updated_at = res.avatar_updated_at
    },

    async removeAvatar() {
      await $fetch('/api/users/me/avatar', { method: 'DELETE' })
      if (this.user) this.user.avatar_updated_at = null
    },

    async logout() {
      await $fetch('/api/auth/logout', { method: 'POST' })
      this.user = null
    },
  },
})
