import ReconnectingWebSocket from "reconnecting-websocket"
import { persisted } from "svelte-persisted-store"
import { get, writable } from "svelte/store"
import { protocol_version } from "../../../constants.json"
import { capitalize } from "./utils"

export const password = persisted("password", "")
export const serverUrl = persisted("server-url", "")

const urlFromParams = new URLSearchParams(window.location.search).get("url")
if (urlFromParams) {
  serverUrl.set(urlFromParams)
}
export const defaultServerUrl = `ws${location.protocol === "https" ? "s" : ""}://${location.host}/ws`

const dataReset = {
  authenticated: false, // Did authenticate at least once (guaranteed to have state variables)
  connecting: false, // Is currently connected
  connected: false, // Is currently connecting
  failure: null, // If connection failed, here's why
  // state variables below - Matches what comes from API vintage_pi_tv/app.py:REQUIRED_BROADCAST_DATA_KEYS_TO_START
  current_rating: null,
  ratings: null,
  state: null,
  version: null,
  videos_db: null
}

const websocketWritable = () => {
  const { subscribe, set, update } = writable(dataReset)
  const websocketGet = () => get({ subscribe })

  let ws = null

  return {
    subscribe,
    clearFailure() {
      update((data) => ({ ...data, failure: null }))
    },
    send(data) {
      if (ws) {
        ws.send(JSON.stringify(data))
      }
    },
    disconnect(reason = null) {
      if (ws) {
        // Set ws to null before closing so failure reason doesn't propagate and
        // so disconnect() doesn't get called in onclose()
        const _ws = ws
        ws = null
        _ws.close()
      }
      set({ ...dataReset, failure: reason })
    },
    connect() {
      this.disconnect()
      let url

      try {
        url = new URL(get(serverUrl) || defaultServerUrl)
        if (!/^wss?:$/i.test(url.protocol)) {
          this.disconnect("Server URL must start with ws:// or wss://")
          return
        }
      } catch (err) {
        this.disconnect("Invalid server URL")
        return
      }

      update((data) => ({ ...data, connecting: true }))

      ws = new ReconnectingWebSocket(get(serverUrl) || defaultServerUrl, undefined, {
        maxEnqueuedMessages: 0,
        minReconnectionDelay: 1000,
        maxReconnectionDelay: 2000
      })

      ws.onopen = () => {
        this.send({ password: get(password), protocol_version })
      }

      ws.onmessage = (event) => {
        const msg = JSON.parse(event.data)
        update((data) => ({ ...data, ...msg, authenticated: true, connecting: false, connected: true, failure: null }))
      }

      ws.onclose = (event) => {
        if (ws) {
          if (event.code >= 4000) {
            console.error(`"Disconnected from websocket on purpose! (${event.reason})`)
            this.disconnect(event.reason)
          } else {
            if (websocketGet().authenticated) {
              update((data) => ({ ...data, connected: false, connecting: true }))
            } else {
              this.disconnect(capitalize(event.reason || "Problem connecting, try again"))
            }
          }
        }
      }
    }
  }
}

export const websocket = websocketWritable()
