<script>
  import { websocket } from "./../websocket"
  import { states } from "../../../../constants.json"

  let extraClasses = ""
  export { extraClasses as class }
  export let icon = ""
  export let action
  export let extras = {}
  export let isSquare = true

  $: disabled = ![states.playing, states.paused].includes($websocket.state.state)
</script>

<button
  class="btn btn-neutral {isSquare && 'btn-square'} join-item btn-sm sm:btn-md lg:btn-lg {extraClasses || ''}"
  on:click|preventDefault={() => websocket.action(action, extras)}
  {disabled}
  {...$$restProps}
>
  {#if icon}
    <span class={`${icon} h-5 w-5 sm:h-8 sm:w-8 lg:h-10 lg:w-10`}></span>
  {/if}
  <slot />
</button>
