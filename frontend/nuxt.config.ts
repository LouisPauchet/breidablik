// https://nuxt.com/docs/api/configuration/nuxt-config
export default defineNuxtConfig({
  compatibilityDate: '2025-07-15',
  devtools: { enabled: true },
  modules: ['@pinia/nuxt', '@vite-pwa/nuxt'],

  // SSR is explicitly off: Nuxt is used here purely as a static-SPA generator (file-based
  // routing + auto-imports), never as a running Node server — `nuxt generate` with this
  // setting produces a plain static folder that FastAPI serves like any other static build,
  // identically under Docker or Passenger. Do not flip this on without re-checking the
  // deployment story (see plan doc, Architecture & deployment).
  ssr: false,
  nitro: {
    preset: 'static',
  },

  vite: {
    server: {
      proxy: {
        '/api': 'http://localhost:8000',
      },
    },
  },

  app: {
    pageTransition: { name: 'page', mode: 'out-in' },
    head: {
      htmlAttrs: { lang: 'en' },
      title: 'Breidablik',
      link: [
        // iOS Safari doesn't fully honor the web manifest — these are the separate,
        // Apple-specific tags it actually reads for home-screen install styling.
        { rel: 'apple-touch-icon', href: '/icons/apple-touch-icon.png' },
      ],
      meta: [
        { name: 'description', content: 'Household collective manager: duties, tasks, events, shopping lists.' },
        { name: 'apple-mobile-web-app-capable', content: 'yes' },
        { name: 'apple-mobile-web-app-status-bar-style', content: 'default' },
        { name: 'theme-color', content: '#0f766e' },
      ],
    },
  },

  pwa: {
    strategies: 'injectManifest',
    srcDir: 'service-worker',
    filename: 'sw.ts',
    injectManifest: {
      globPatterns: ['**/*.{js,css,html,png,svg,ico,woff2}'],
    },
    manifest: {
      name: 'Breidablik',
      short_name: 'Breidablik',
      description: 'Household collective manager: duties, tasks, events, shopping lists.',
      theme_color: '#0f766e',
      background_color: '#ffffff',
      display: 'standalone',
      start_url: '/',
      scope: '/',
      icons: [
        { src: '/icons/icon-192.png', sizes: '192x192', type: 'image/png' },
        { src: '/icons/icon-512.png', sizes: '512x512', type: 'image/png' },
        { src: '/icons/icon-512-maskable.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
      ],
    },
    devOptions: {
      enabled: true,
      type: 'module',
    },
  },
})
