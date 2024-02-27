<script>
  import { websocket } from "./websocket"
  import { states } from "../../../constants.json"
  import { isViewableBasedOnCurrentRating, formatDuration, colorForRating } from "./utils"
  import PlayButton from "./components/PlayButton.svelte"

  let showRemaining = false

  $: connected = $websocket.connected
  $: current = $websocket.state.video
  $: currentRating = $websocket.current_rating
  $: disabled = !isPlayingOrPaused
  $: duration = $websocket.state.duration
  $: durationPretty = formatDuration(duration)
  $: state = $websocket.state.state
  $: isPaused = state === states.paused
  $: isPlaying = state === states.playing
  $: isPlayingOrPaused = isPlaying || isPaused
  $: pausePulseClasses = isPaused ? "text-error progress-error animate-pulse" : ""
  $: position = $websocket.state.position
  $: percentDone = duration > 0 ? (position / duration) * 100 : 0
  $: positionPretty = formatDuration(position, duration >= 3600)
  $: ratings = $websocket.ratings
  $: remainingPretty = `-${formatDuration(duration - position, duration >= 3600)}`
  $: [volume, muted] = $websocket.volume

  const progressBarSeek = (event) => {
    if (isPlayingOrPaused && duration > 0) {
      websocket.action("seek", { position: (event.offsetX / event.target.clientWidth) * duration })
    }
  }

  const seekButtons = [
    ["icon-[mdi--rewind-60]", "left", { seconds: 60 }],
    ["icon-[mdi--rewind-15]", "left", { seconds: 15 }],
    ["icon-[mdi--fast-forward-15]", "right", { seconds: 15 }],
    ["icon-[mdi--fast-forward-60]", "right", { seconds: 60 }]
  ]
</script>

<div class="flex flex-col gap-2 overflow-hidden px-2 sm:gap-3 xl:px-1">
  <!-- Filename header -->
  <div class="flex items-center justify-center text-base sm:text-lg md:text-2xl lg:text-3xl">
    {#if isPlayingOrPaused}
      <div class="truncate font-bold italic {pausePulseClasses}">
        {current.name}
      </div>
    {:else if state === states.loading}
      <span class="text-warning">Loading...</span>
    {:else if state === states.needs_files}
      <span class="animate animate-pulse font-bold italic text-error">No video files detected!</span>
    {/if}
  </div>

  <!-- Playbar -->
  <!-- svelte-ignore a11y-click-events-have-key-events ally-no a11y-no-noninteractive-element-interactions a11y-no-static-element-interactions -->
  <div class="flex items-center gap-2 text-sm leading-none sm:text-base lg:text-2xl">
    <div class={pausePulseClasses}>{positionPretty}</div>
    <progress
      class="progress h-4 cursor-pointer sm:h-6 lg:h-8 {pausePulseClasses}"
      value={percentDone}
      max="100"
      on:click|preventDefault={progressBarSeek}
    />
    <div class="cursor-pointer ${pausePulseClasses}" on:click={() => (showRemaining = !showRemaining)}>
      {showRemaining ? remainingPretty : durationPretty}
    </div>
  </div>

  <!-- Buttons -->
  <div class="join flex items-center justify-center sm:mt-1">
    <PlayButton
      class={isPaused && "btn-error animate-pulse"}
      icon={isPaused ? "icon-[mdi--play]" : "icon-[mdi--pause]"}
      action="pause"
      {disabled}
    />
    <PlayButton icon="icon-[mdi--shuffle-variant]" action="random" />
    {#each seekButtons as [icon, action, extras]}
      <PlayButton {icon} {action} {extras} />
    {/each}
    <PlayButton
      icon={muted ? "icon-[mdi--volume-high]" : "icon-[mdi--mute]"}
      class={muted && "btn-warning animate-pulse"}
      action="mute"
    />
    <PlayButton icon="icon-[mdi--volume-minus]" action="volume-down" />
    <div
      class="join-item flex h-full w-12 items-center justify-center bg-base-200 px-1 text-sm sm:w-14 sm:text-base md:w-16 md:text-lg"
      class:text-warning={muted}
      class:text-success={!muted && volume >= 100}
      class:text-error={!muted && volume <= 0}
      class:bg-neutral={!isPlayingOrPaused}
      class:bg-opacity-20={!isPlayingOrPaused}
    >
      {muted ? "muted" : `${volume}%`}
    </div>
    <PlayButton icon="icon-[mdi--volume-plus]" action="volume-up" />

    {#if currentRating}
      <PlayButton action="ratings" style="color: {colorForRating(currentRating, ratings)}">{currentRating}</PlayButton>
    {/if}
  </div>
</div>

<div class="overflow-y-auto border border-base-content">
  <div class="flex flex-col gap-2 py-2">
    {#each $websocket.videos_db as video}
      <div class="flex items-center justify-between gap-2 px-2 py-0.5">
        <button
          class="btn btn-primary flex flex-1 justify-start truncate"
          on:click={() => websocket.action("play", { path: video.path })}
          disabled={!isPlayingOrPaused}
        >
          {video.channel}. {video.name} [is_viewable={isViewableBasedOnCurrentRating(
            video.rating,
            currentRating,
            ratings
          )}]
          {#if video.rating}
            {@const color = colorForRating(video.rating, ratings)}
            <div style="color: {color}">{video.rating}</div>
          {/if}
        </button>

        {#if video.path === current?.path}
          <div class="badge badge-accent">Current</div>
        {/if}
      </div>
    {/each}
  </div>
</div>
