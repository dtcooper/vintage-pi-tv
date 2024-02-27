<script>
  import { websocket } from "./websocket"
  import { states } from "../../../constants.json"
  import { isViewableBasedOnCurrentRating, formatDuration } from "./utils"

  $: current = $websocket.state.video
  $: position = $websocket.state.position
  $: duration = $websocket.state.duration
  $: positionPretty = formatDuration(position, duration >= 3600)
  $: durationPretty = formatDuration(duration)
  $: connected = $websocket.connected
  $: state = $websocket.state.state
  $: currentRating = $websocket.current_rating
  $: ratings = $websocket.ratings
  $: isPlaying = [states.playing, states.paused].includes(state)
  $: percentDone = duration > 0 ? (position / duration) * 100 : 0

  const seek = (event) => {
    if (isPlaying && duration > 0) {
      websocket.action("seek", { position: (event.offsetX / event.target.clientWidth) * duration })
    }
  }
</script>

<div class="flex flex-col gap-2 overflow-hidden px-2 lg:px-0">
  <!-- Filename header -->
  <div class="flex items-center justify-center">
    {#if [states.playing, states.paused].includes(state)}
      <div class="truncate font-bold italic" class:text-warning={state === states.paused}>
        {current.name}
      </div>
    {:else if state === states.loading}
      Loading
    {:else if state === states.needs_files}
      <span class="animate animate-pulse font-bold italic text-error">No video files detected!</span>
    {/if}
  </div>

  <!-- Playbar -->
  <div class="flex items-center gap-2 leading-none">
    <div>{positionPretty}</div>
    <progress class="progress h-5" value={percentDone} max="100" on:click|preventDefault={seek} />
    <div>{durationPretty}</div>
  </div>

  <button class="btn" on:click={() => websocket.action("pause")}>
    {#if state === states.paused}Play{:else}Pause{/if}
  </button>
  <button class="btn" on:click={() => websocket.action("random")}>Random</button>
</div>

<div class="overflow-y-auto border border-base-content p-0.5">
  {#each $websocket.videos_db as video}
    <div>
      <button class="font-slim btn btn-sm font-normal" on:click={() => websocket.action("play", { path: video.path })}>
        {video.channel}. {video.name} [is_viewable={isViewableBasedOnCurrentRating(
          video.rating,
          currentRating,
          ratings
        )}]
      </button>
      {#if video.path === current?.path}
        <span class="badge badge-accent">Current</span>
      {/if}
    </div>
  {/each}
</div>
