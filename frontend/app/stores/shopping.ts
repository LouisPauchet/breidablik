export interface ShoppingItem {
  id: string
  list_id: string
  name: string
  quantity: string | null
  is_checked: boolean
  added_by_id: string
  checked_by_id: string | null
  checked_at: string | null
  created_at: string
}

export interface ShoppingList {
  id: string
  name: string
  owner_user_id: string | null
  duty_id: string | null
  created_by_id: string
  created_at: string
  items: ShoppingItem[]
}

export interface ShoppingListCreatePayload {
  name: string
  is_private: boolean
  duty_id?: string | null
}

export const useShoppingStore = defineStore('shopping', {
  state: () => ({
    lists: [] as ShoppingList[],
    current: null as ShoppingList | null,
  }),
  actions: {
    async fetchLists() {
      this.lists = await $fetch<ShoppingList[]>('/api/shopping/lists')
    },

    async fetchList(id: string) {
      this.current = await $fetch<ShoppingList>(`/api/shopping/lists/${id}`)
      return this.current
    },

    async createList(payload: ShoppingListCreatePayload) {
      const created = await $fetch<ShoppingList>('/api/shopping/lists', {
        method: 'POST',
        body: payload,
      })
      this.lists.push(created)
      return created
    },

    async deleteList(id: string) {
      await $fetch(`/api/shopping/lists/${id}`, { method: 'DELETE' })
      this.lists = this.lists.filter((l) => l.id !== id)
    },

    async addItem(listId: string, name: string, quantity?: string | null) {
      const item = await $fetch<ShoppingItem>(`/api/shopping/lists/${listId}/items`, {
        method: 'POST',
        body: { name, quantity: quantity || null },
      })
      if (this.current?.id === listId) this.current.items.push(item)
      return item
    },

    async toggleChecked(itemId: string) {
      const updated = await $fetch<ShoppingItem>(`/api/shopping/items/${itemId}/toggle-checked`, {
        method: 'PATCH',
      })
      if (this.current) {
        const idx = this.current.items.findIndex((i) => i.id === itemId)
        if (idx !== -1) this.current.items[idx] = updated
      }
      return updated
    },

    async deleteItem(itemId: string) {
      await $fetch(`/api/shopping/items/${itemId}`, { method: 'DELETE' })
      if (this.current) {
        this.current.items = this.current.items.filter((i) => i.id !== itemId)
      }
    },
  },
})
