<script>
  import { onMount } from "svelte"
  import Footer from "./lib/Footer.svelte"
  import { websocket } from "./lib/websocket"
  import Login from "./lib/Login.svelte"
  import Main from "./lib/Main.svelte"

  $: authenticated = $websocket.authenticated

  onMount(() => websocket.connect()) // Autoconnect on start
</script>

{#if !authenticated}
  <Login />
{/if}

<div class="mx-auto flex h-screen max-h-screen max-w-screen-lg flex-col">
  <header class="mt-3 flex items-center justify-center gap-x-4 sm:gap-x-10">
    <span class="icon-[icon-park-solid--tv-one] h-8 w-8 sm:h-12 sm:w-12"></span>
    <h1 class="text-3xl font-bold italic underline sm:text-5xl">Vintage Pi TV</h1>
    <span class="icon-[icon-park-solid--tv-one] h-8 w-8 sm:h-12 sm:w-12"></span>
  </header>
  <main class="mt-2 flex flex-1 flex-col">
    {#if authenticated}
      <Main />
    {/if}
  </main>
  <Footer />
</div>
