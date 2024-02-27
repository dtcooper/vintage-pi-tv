<script>
  import { websocket, password, defaultServerUrl, serverUrl } from "./websocket"
  import { persisted } from "svelte-persisted-store"
  import { slide } from "svelte/transition"
  import Modal from "./components/Modal.svelte"

  let disabled = false
  let revealPassword = false
  const showServerUrl = persisted("show-server-url", false)

  $: disabled = $websocket.connecting
</script>

<Modal title="Please Log In" icon="icon-[mdi--login]" submit={() => websocket.connect()}>
  <div class="form-control w-full">
    <div class="label">
      <span class="label-text">Password:</span>
      {#if $websocket.failure}
        <span class="label-text-alt text-right text-error">{$websocket.failure}</span>
      {/if}
    </div>
    {#if revealPassword}
      <input
        {disabled}
        bind:value={$password}
        on:input={() => websocket.clearFailure()}
        class:input-error={$websocket.failure}
        class="input input-bordered"
        placeholder="Enter password..."
        type="text"
        autocapitalize="none"
        autocomplete="off"
        autocorrect="off"
      />
    {:else}
      <input
        {disabled}
        bind:value={$password}
        on:input={() => websocket.clearFailure()}
        class:input-error={$websocket.failure}
        class:tracking-wider={!revealPassword && $password}
        class="input input-bordered"
        placeholder="Enter password..."
        type="password"
        autocapitalize="none"
        autocomplete="off"
        autocorrect="off"
      />
    {/if}
    <div class="flex justify-between">
      <div class="form-control items-end">
        <label class="label cursor-pointer gap-x-3 pr-0">
          <input {disabled} type="checkbox" class="checkbox" bind:checked={$showServerUrl} />
          <span class="label-text">{$showServerUrl ? "Hide" : "Show"} server URL</span>
        </label>
      </div>
      <div class="form-control items-end">
        <label class="label cursor-pointer gap-x-3 pr-0">
          <span class="label-text">{revealPassword ? "Hide" : "Reveal"} password</span>
          <input {disabled} type="checkbox" class="checkbox" bind:checked={revealPassword} />
        </label>
      </div>
    </div>
  </div>

  {#if $showServerUrl}
    <div transition:slide>
      <div class="form-control w-full">
        <div class="label">
          <span class="label-text">Server URL:</span>
        </div>
        <input
          {disabled}
          bind:value={$serverUrl}
          on:input={() => websocket.clearFailure()}
          class:input-error={$websocket.failure}
          class="input input-bordered"
          placeholder={defaultServerUrl}
          type="text"
          autocapitalize="none"
          autocomplete="off"
          autocorrect="off"
        />
      </div>
      <div class="flex justify-end pt-2">
        <button
          class="btn btn-secondary btn-xs italic"
          disabled={!$serverUrl || disabled}
          type="button"
          on:click={() => ($serverUrl = "")}
        >
          Reset to default
        </button>
      </div>
    </div>
  {/if}

  <svelte:fragment slot="action">
    <button
      type="button"
      class="btn btn-error"
      disabled={!$websocket.connecting}
      on:click={() => websocket.disconnect()}>Disconnect</button
    >
    <button type="submit" class="btn btn-primary" {disabled}>Log in</button>
  </svelte:fragment>
</Modal>
