<script>
  import { websocket } from "./websocket"
  import { states } from "../../../constants.json"

  const action = (name, extras) => {
    websocket.send({ action: name, ...extras })
  }

  $: current = $websocket.state.video
  $: position = $websocket.state.position
  $: duration = $websocket.state.duration
  $: connected = $websocket.connected
  $: state = $websocket.state.state
</script>

<div class="flex h-0 min-h-full flex-col">
  <div>
    Video: {current ? current.name : "Loading"} / State: {state} / {position}/{duration}<br />
    <button class="btn" on:click={() => action("pause")}>
      {#if state === states.paused}Play{:else}Pause{/if}
    </button>
    <button class="btn" on:click={() => action("random")}> Random </button>
  </div>
  <div class="flex-1 overflow-auto bg-blue-500">
    <div class="flex flex-col gap-1 p-1">
      {#each $websocket.videos_db as video}
        <div>
          <button class="btn btn-sm" on:click={() => action("play", { path: video.path })}>
            {video.channel}. {video.name}
          </button>
          {#if video.path === current?.path}
            <span class="badge badge-accent">Current</span>
          {/if}
        </div>
      {/each}
    </div>
  </div>
</div>