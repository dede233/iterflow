<script setup lang="ts">
// Lightweight stroke icon set; avoids adding an icon dependency.
defineProps<{ name: string; size?: number }>()
const PATHS: Record<string, string> = {
  home: 'M3 10.5 12 3l9 7.5V20a1 1 0 0 1-1 1h-5v-6h-6v6H4a1 1 0 0 1-1-1z',
  feedback: 'M4 5h16v11H8l-4 4z M8 9h8 M8 12h5',
  requirement: 'M6 3h9l4 4v14H6z M14 3v5h5 M9 13h7 M9 17h5',
  version: 'M12 3 3 8l9 5 9-5z M3 13l9 5 9-5',
  release: 'M5 19c3-1 4-4 4-4l-3-3s-3 1-4 4 M9 15l6-6c2-2 4-5 5-6-1 1-4 3-6 5l-6 6 M14 5l5 5',
  bell: 'M6 16V11a6 6 0 1 1 12 0v5l2 2H4z M10 21h4',
  audit: 'M12 3 4 6v6c0 5 3.5 8 8 9 4.5-1 8-4 8-9V6z M9 12l2 2 4-4',
  system: 'M3 3h8v8H3z M13 3h8v8h-8z M3 13h8v8H3z M13 13h8v8h-8z',
  users: 'M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8z M2 21c0-4 3-6 7-6s7 2 7 6 M17 11a3 3 0 1 0 0-6 M22 20c0-3-2-5-5-5',
  shield: 'M12 3 4 6v6c0 5 3.5 8 8 9 4.5-1 8-4 8-9V6z',
  user: 'M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8z M4 21c0-4 4-6 8-6s8 2 8 6',
  logout: 'M15 4h4v16h-4 M10 8l-4 4 4 4 M6 12h10',
  plus: 'M12 5v14 M5 12h14',
  filter: 'M4 5h16l-6 8v6l-4-2v-4z',
  search: 'M11 18a7 7 0 1 0 0-14 7 7 0 0 0 0 14z M20 20l-4-4',
  chevron: 'M9 6l6 6-6 6',
  back: 'M15 6l-6 6 6 6',
  paperclip: 'M20 12l-8 8a5 5 0 0 1-7-7l9-9a3 3 0 0 1 4 4l-9 9a1 1 0 0 1-2-2l8-8',
  comment: 'M4 5h16v11H8l-4 4z',
  inbox: 'M3 13l3-8h12l3 8v6H3z M3 13h5l1 2h6l1-2h5',
  alert: 'M12 3 2 20h20z M12 9v5 M12 17h.01',
  lock: 'M6 11h12v10H6z M8 11V7a4 4 0 0 1 8 0v4',
}
</script>

<template>
  <svg
    :width="size ?? 18" :height="size ?? 18" viewBox="0 0 24 24" fill="none" stroke="currentColor"
    stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" class="app-icon"
  >
    <path :d="PATHS[name] ?? ''" />
  </svg>
</template>

<style scoped>
.app-icon { flex-shrink: 0; }
</style>
