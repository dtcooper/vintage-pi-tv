<script>
  import { websocket } from "./websocket"
  import { states } from "../../../constants.json"
  import { isViewableBasedOnCurrentRating, formatDuration } from "./utils"
  import PlayButton from "./components/PlayButton.svelte"
  import { each } from "svelte/internal"

  let showRemaining = false

  $: current = $websocket.state.video
  $: position = $websocket.state.position
  $: duration = $websocket.state.duration
  $: positionPretty = formatDuration(position, duration >= 3600)
  $: durationPretty = formatDuration(duration)
  $: remainingPretty = `-${formatDuration(duration - position, duration >= 3600)}`
  $: connected = $websocket.connected
  $: state = $websocket.state.state
  $: currentRating = $websocket.current_rating
  $: ratings = $websocket.ratings
  $: isPlaying = state === states.playing
  $: isPaused = state === states.paused
  $: isPlayingOrPaused = isPlaying || isPaused
  $: percentDone = duration > 0 ? (position / duration) * 100 : 0
  $: pausePulseClasses = isPaused ? "text-error progress-error animate-pulse" : ""
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

<div class="flex flex-col gap-2 overflow-hidden px-2 sm:gap-3 lg:px-0">
  <!-- Filename header -->
  <div class="flex items-center justify-center text-base sm:text-lg md:text-2xl">
    {#if isPlayingOrPaused}
      <div class={`truncate font-bold italic ${pausePulseClasses}`}>
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
  <div class="flex items-center gap-2 text-sm leading-none sm:text-base md:text-xl">
    <div class={pausePulseClasses}>{positionPretty}</div>
    <progress
      class={`progress h-5 cursor-pointer sm:h-6 md:h-7 ${pausePulseClasses}`}
      value={percentDone}
      max="100"
      on:click|preventDefault={progressBarSeek}
    />
    <div class={`cursor-pointer ${pausePulseClasses}`} on:click={() => (showRemaining = !showRemaining)}>
      {showRemaining ? remainingPretty : durationPretty}
    </div>
  </div>

  <!-- Buttons -->
  <div class="join flex items-center justify-center sm:mt-1">
    <PlayButton
      class={isPaused && "btn-success animate-pulse"}
      icon={isPaused ? "icon-[mdi--play-circle]" : "icon-[mdi--pause-circle]"}
      on:click={() => websocket.action("pause")}
    />
    {#each seekButtons as [icon, action, extras]}
      <PlayButton {icon} on:click={() => websocket.action(action, extras)} />
    {/each}
    <PlayButton
      icon={muted ? "icon-[mdi--volume-high]" : "icon-[mdi--mute]"}
      class={muted && "btn-warning animate-pulse"}
      on:click={() => websocket.action("mute")}
    />
    <PlayButton icon="icon-[mdi--volume-minus]" on:click={() => websocket.action("volume-down")} />
    <div
      class="join-item flex h-full w-12 items-center justify-center bg-base-200 px-1 text-sm sm:w-14 sm:text-base md:w-16 md:text-lg"
      class:text-warning={muted}
      class:text-success={!muted && volume >= 100}
      class:text-error={!muted && volume <= 0}
    >
      {muted ? "muted" : `${volume}%`}
    </div>
    <PlayButton icon="icon-[mdi--volume-plus]" on:click={() => websocket.action("volume-up")} />
    <PlayButton icon="icon-[mdi--shuffle-variant]" on:click={() => websocket.action("random")}>Random</PlayButton>
  </div>
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
