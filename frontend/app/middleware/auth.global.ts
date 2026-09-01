export default defineNuxtRouteMiddleware(async (to) => {
  const authStore = useAuthStore()

  if (!authStore.initialized) {
    await authStore.fetchMe()
  }

  const isPublicPath = to.path === '/login' || to.path.startsWith('/invite/')

  if (!authStore.user && !isPublicPath) {
    return navigateTo('/login')
  }
  if (authStore.user && to.path === '/login') {
    return navigateTo('/')
  }
})
