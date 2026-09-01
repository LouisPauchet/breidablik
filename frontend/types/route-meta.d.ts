export {}

declare module 'vue-router' {
  interface RouteMeta {
    // Set by pages/dashboard/[token].vue to opt out of the app shell's mobile-width column,
    // bottom nav, and login-only prompts — that page is a full-viewport wall display reached
    // via a public link, not a normal in-app screen.
    fullBleed?: boolean
  }
}
