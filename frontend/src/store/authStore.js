import { create } from 'zustand'
import { persist, createJSONStorage } from 'zustand/middleware'

export const useAuthStore = create(
  persist(
    (set, get) => ({
      user: null,
      accessToken: null,
      refreshToken: null,
      school: null,
      isHydrated: false, // true once boot-time session check has run

      setAuth: (user, accessToken, refreshToken, tenant = null) => {
        set({ user, accessToken, refreshToken, school: tenant, isHydrated: true })
      },

      // Used ONLY by the silent token-refresh flow in api/client.js.
      // Updates the access token without touching user/school/refreshToken
      // at all — this is what setAuth's optional `tenant` param previously
      // got wrong: a refresh-triggered setAuth(user, newToken, refreshToken)
      // call with no 4th argument silently defaulted `school` to null,
      // wiping branding back to defaults on every token refresh. Giving
      // refresh its own narrow action makes that class of bug impossible
      // going forward, regardless of what setAuth's signature does later.
      setAccessToken: (accessToken) => set({ accessToken }),

      setUser: (user) => set({ user }),

      setSchool: (school) => set({ school }),

      setHydrated: (value) => set({ isHydrated: value }),

      logout: () => {
        set({ user: null, accessToken: null, refreshToken: null, school: null, isHydrated: true })
      },

      isAuthenticated: () => !!get().user && !!get().accessToken,

      hasRole: (...roles) => {
        const user = get().user
        return user ? roles.includes(user.role) : false
      },
    }),
    {
      name: 'auth-storage-v3',
      // sessionStorage is scoped per-tab, unlike localStorage which is shared
      // across every tab/window of the same origin. This is what keeps two
      // logins in two tabs (e.g. admin in one, teacher in another) from
      // clobbering each other's tokens.
      storage: createJSONStorage(() => sessionStorage),
      partialize: (state) => ({
        // school is NOT persisted — it must come from login response each time
        // to avoid cross-tenant color leaking
        user: state.user,
        accessToken: state.accessToken,
        refreshToken: state.refreshToken,
        // isHydrated is NOT persisted — it must always start false on boot
        // so the app re-validates the session instead of trusting stale state.
      }),
    }
  )
)