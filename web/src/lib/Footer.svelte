<script>
  import { websocket } from "./websocket"

  const version = __VERSION__

  $: authenticated = $websocket.authenticated
  $: connected = $websocket.connected
  $: connecting = $websocket.connecting
</script>

<footer class="mx-1 grid h-8 items-center gap-1 px-0.5 sm:px-1" class:grid-cols-[1fr_auto_1fr]={authenticated}>
  {#if authenticated}
    <div class="flex items-center gap-1">
      <span class="text-xs leading-none">Status:</span>
      <span
        class="badge badge-outline badge-sm font-bold sm:badge-md"
        class:badge-success={connected}
        class:badge-error={connecting}
        class:animate={connecting}
        class:animate-pulse={connecting}
      >
        {#if connected}
          Connected
        {:else if connecting}
          Reconnecting...
        {/if}
      </span>
    </div>
  {/if}
  <div class="text-center text-xs sm:text-sm md:text-base">
    <a
      href="https://github.com/dtcooper/vintage-pi-tv"
      target="_blank"
      class="link-hover link link-primary font-bold italic"
    >
      Vintage Pi TV
    </a>
    <div class="hidden sm:inline">
      ({version})
    </div>
  </div>
  {#if authenticated}
    <div class="leading-0 flex items-center justify-end">
      <button class="btn btn-error btn-xs italic" on:click={() => websocket.disconnect()}>Log out</button>
    </div>
  {/if}
</footer>
