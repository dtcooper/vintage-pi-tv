<script>
  import { websocket } from "./websocket"
  import { states } from "../../../constants.json"
  import { isViewableBasedOnCurrentRating, formatDuration } from "./utils"
  import PlayButton from "./components/PlayButton.svelte"
  import RatingBadge from "./components/RatingBadge.svelte"

  let showRemaining = false

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

  let lastVideo
  let elements = {}
  $: elements = Object.fromEntries(Object.entries(elements).filter(([_, v]) => !!v)) // Remove empty keys
  $: if (lastVideo?.path !== current?.path) {
    lastVideo = current
    if (current) {
      elements[current.path]?.scrollIntoView({ behavior: "smooth", block: "center" }, 25)
    }
  }

  const progressBarSeek = (event) => {
    if (isPlayingOrPaused && duration > 0) {
      websocket.action("seek", { position: (event.offsetX / event.target.clientWidth) * duration })
    }
  }

  const seekButtons = [
    // icon, action, extras, hideSmall
    ["icon-[mdi--rewind-60]", "left", { seconds: 60 }, true],
    ["icon-[mdi--rewind-15]", "left", { seconds: 15 }, false],
    ["icon-[mdi--fast-forward-15]", "right", { seconds: 15 }, false],
    ["icon-[mdi--fast-forward-60]", "right", { seconds: 60 }, true]
  ]
</script>

<div class="mt-2 flex flex-col gap-3 overflow-hidden px-2 md:gap-4 lg:gap-5 xl:px-1">
  <!-- Filename header -->
  <div class="flex items-center justify-center text-base sm:text-lg md:text-2xl lg:text-3xl">
    {#if isPlayingOrPaused}
      <div class="truncate font-bold italic {pausePulseClasses}">
        {current.channel}. {current.name}
      </div>
    {:else if state === states.loading}
      <span class="animate-pulse text-warning">Loading...</span>
    {:else if state === states.needs_files}
      <span class="animate-pulse font-bold italic text-error">No video files detected!</span>
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
    <PlayButton icon="icon-[mdi--rewind]" action="rewind" />
    {#each seekButtons as [icon, action, extras, hideSmall]}
      <PlayButton class={hideSmall && "hidden md:flex"} {icon} {action} {extras} />
    {/each}
    <PlayButton
      icon={muted ? "icon-[mdi--volume-high]" : "icon-[mdi--mute]"}
      class={muted && "btn-warning animate-pulse"}
      action="mute"
    />
    <PlayButton icon="icon-[mdi--volume-minus]" action="volume-down" />
    <div
      class="join-item flex h-full w-12 items-center justify-center bg-neutral px-1 text-sm text-neutral-content sm:w-14 sm:text-base md:w-16 md:text-lg"
      class:text-neutral-content={!muted && volume > 0 && volume < 100}
      class:text-warning={muted}
      class:text-success={!muted && volume >= 100}
      class:text-error={!muted && volume <= 0}
    >
      {muted ? "muted" : `${volume}%`}
    </div>
    <PlayButton icon="icon-[mdi--volume-plus]" action="volume-up" />

    {#if currentRating}
      <PlayButton action="ratings" isSquare={false}>
        <RatingBadge rating={currentRating} />
      </PlayButton>
    {/if}
  </div>
</div>

<!-- Playlist -->
<div class="mt-1 overflow-y-auto border border-base-content sm:mt-2">
  <div class="flex flex-col gap-2 py-2">
    {#each $websocket.videos_db as video}
      {@const isViewable = isViewableBasedOnCurrentRating(video.rating, currentRating, ratings)}
      {@const isCurrent = video.path === current?.path}
      <div class="flex items-center justify-between gap-2 px-2 py-0.5" bind:this={elements[video.path]}>
        <button
          class="btn btn-sm flex flex-1 justify-start overflow-hidden sm:btn-md md:btn-lg"
          class:pointer-events-none={!isViewable || isCurrent}
          class:cursor-auto={!isViewable || isCurrent}
          class:btn-secondary={isCurrent}
          class:btn-neutral={!isCurrent}
          disabled={!isCurrent && (!isPlayingOrPaused || !isViewable)}
          on:click={() => websocket.action("play", { path: video.path })}
        >
          <span class="font-bold">{video.channel}.</span>
          <span class="flex-1 truncate text-left font-normal italic">{video.name}</span>
          {#if video.rating}
            <RatingBadge rating={video.rating} />
          {/if}
        </button>
      </div>
    {/each}
  </div>
</div>
