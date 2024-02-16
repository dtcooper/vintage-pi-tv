<script>
  import { onMount } from 'svelte';
  import Counter from './lib/Counter.svelte'

  onMount(() => console.log("Mounted!"))
</script>

<main>
  <h1 class="banner">Vintage Pi TV</h1>

  <div>
    <Counter />
  </div>
</main>

<style lang="postcss">
  .banner {
    @apply text-5xl;
  }
</style>
