import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export const useAuthStore = create(
  persist(
    (set, get) => ({
      user: null,
      accessToken: null,
      refreshToken: null,
      school: null,       // Tenant branding info

      // ── Actions ────────────────────────────────────────────────────────────

      setAuth: (user, accessToken, refreshToken) => {
        localStorage.setItem('access_token', accessToken)
        localStorage.setItem('refresh_token', refreshToken)
        set({ user, accessToken, refreshToken })
      },

      setSchool: (school) => set({ school }),

      logout: () => {
        localStorage.removeItem('access_token')
        localStorage.removeItem('refresh_token')
        set({ user: null, accessToken: null, refreshToken: null, school: null })
      },

      // ── Computed ───────────────────────────────────────────────────────────

      isAuthenticated: () => !!get().user && !!get().accessToken,

      hasRole: (...roles) => {
        const user = get().user
        return user ? roles.includes(user.role) : false
      },
    }),
    {
      name: 'auth-storage',
      // Only persist non-sensitive fields
      partialize: (state) => ({
        user: state.user,
        school: state.school,
        // Tokens stored separately in localStorage by setAuth()
      }),
    }
  )
)