let listeners = []

export const toastBus = {
  subscribe(fn) {
    listeners.push(fn)
    return () => {
      listeners = listeners.filter((listener) => listener !== fn)
    }
  },
  emit(message, type) {
    listeners.forEach((fn) => fn(message, type))
  },
}