<script>
  import { websocket } from "./websocket"

  const version = __VERSION__

  $: authenticated = $websocket.authenticated
  $: connected = $websocket.connected
  $: connecting = $websocket.connecting
</script>

<footer class="mx-1 mt-1 grid h-8 items-center gap-1" class:grid-cols-[1fr_auto_1fr]={authenticated}>
  {#if authenticated}
    <div>
      <span class="text-xs sm:text-sm">Status:</span>
      <span
        class="badge badge-outline font-bold"
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
  <div class="text-center text-xs sm:text-sm">
    <a href="https://github.com/dtcooper/vintage-pi-tv" target="_blank" class="link-hover link link-primary">
      Vintage Pi TV
    </a>
    (Version: <code class="py mx-0.5 rounded-sm bg-base-300 px-1 py-0.5">{version}</code>)
  </div>
  {#if authenticated}
    <div class="flex justify-end">
      <button class="btn btn-error btn-xs italic" on:click={() => websocket.disconnect()}>Log out</button>
    </div>
  {/if}
</footer>
