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

<div
  class="mx-auto grid h-screen max-w-screen-xl gap-2 py-0.5 sm:py-1.5"
  class:grid-rows-[auto_auto_1fr_auto]={authenticated}
  class:content-between={!authenticated}
>
  <header class="flex items-center justify-center gap-x-4 sm:gap-x-10">
    <span class="icon-[icon-park-solid--tv-one] h-8 w-8 sm:h-12 sm:w-12"></span>
    <h1 class="text-3xl font-bold italic underline sm:text-5xl">Vintage Pi TV</h1>
    <span class="icon-[icon-park-solid--tv-one] h-8 w-8 sm:h-12 sm:w-12"></span>
  </header>

  {#if authenticated}
    <Main />
  {/if}

  <Footer />
</div>
