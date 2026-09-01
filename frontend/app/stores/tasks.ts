export interface Task {
  id: string
  title: string
  description: string | null
  due_date: string | null
  is_done: boolean
  done_by_id: string | null
  done_at: string | null
  created_by_id: string
  created_at: string
  assignee_user_ids: string[]
}

export interface TaskCreatePayload {
  title: string
  description?: string | null
  due_date?: string | null
  assignee_user_ids: string[]
}

export interface TaskUpdatePayload {
  title?: string
  description?: string | null
  due_date?: string | null
  assignee_user_ids?: string[]
}

export const useTasksStore = defineStore('tasks', {
  state: () => ({
    tasks: [] as Task[],
  }),
  actions: {
    async fetchTasks() {
      this.tasks = await $fetch<Task[]>('/api/tasks')
    },

    async createTask(payload: TaskCreatePayload) {
      const created = await $fetch<Task>('/api/tasks', { method: 'POST', body: payload })
      await this.fetchTasks()
      return created
    },

    async updateTask(taskId: string, payload: TaskUpdatePayload) {
      const updated = await $fetch<Task>(`/api/tasks/${taskId}`, { method: 'PATCH', body: payload })
      // Re-fetch rather than patch in place: editing due_date changes the server-side sort
      // order (soonest due date first), not just this one row's fields.
      await this.fetchTasks()
      return updated
    },

    async toggleDone(taskId: string) {
      const updated = await $fetch<Task>(`/api/tasks/${taskId}/toggle-done`, { method: 'POST' })
      // Re-fetch rather than patch in place: toggling done changes the server-side sort
      // order (incomplete tasks first), not just this one row's fields.
      await this.fetchTasks()
      return updated
    },

    async deleteTask(taskId: string) {
      await $fetch(`/api/tasks/${taskId}`, { method: 'DELETE' })
      this.tasks = this.tasks.filter((t) => t.id !== taskId)
    },
  },
})
