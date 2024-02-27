<script>
  export let icon = ""

  let extraClasses = ""
  export { extraClasses as class }
</script>

<button class="btn join-item btn-sm sm:btn-md md:btn-lg {extraClasses || ''}" on:click|preventDefault {...$$restProps}>
  {#if icon}
    <span class={`${icon} h-5 w-5 sm:h-8 sm:w-8 md:h-12 md:w-12`}></span>
  {/if}
  <slot />
</button>
