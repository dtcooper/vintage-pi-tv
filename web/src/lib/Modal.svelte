<script>
  import { noop } from "svelte/internal"

  export let title
  export let icon = ""
  export let open = true
  export let submit = noop
</script>

<dialog class="modal" class:modal-open={open}>
  <form class="modal-box max-w-screen-sm" on:submit|preventDefault={submit}>
    {#if title}
      <div class="flex items-center gap-x-3">
        {#if icon}
          <span class="{icon} h-8 w-8"></span>
        {/if}
        <h3 class="text-2xl font-bold italic">{title}</h3>
      </div>
    {/if}
    <p class="py-4">
      <slot />
    </p>
    <div class="modal-action">
      <slot name="action" />
    </div>
  </form>
</dialog>
