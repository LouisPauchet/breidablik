export default defineNuxtRouteMiddleware(async (to) => {
  const authStore = useAuthStore()

  if (!authStore.initialized) {
    await authStore.fetchMe()
  }

  if (!authStore.user && to.path !== '/login') {
    return navigateTo('/login')
  }
  if (authStore.user && to.path === '/login') {
    return navigateTo('/')
  }
})
