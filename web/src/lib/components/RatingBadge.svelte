<script>
  import { websocket } from "../websocket"
  import { interpolate, formatHex } from "culori"
  import { isDark } from "daisyui/src/theming/functions"

  const colorForRating = (rating, ratings) => {
    if (ratings) {
      for (const ratingObj of ratings) {
        if (ratingObj.rating === rating) {
          return ratingObj.color
        }
      }
    }
    return "#FFFFFF"
  }

  const backgroundColor = (color) => {
    return formatHex(interpolate([color, isDark(color) ? "white" : "black"], "oklch")(0.6))
  }

  let extraClasses = ""
  export { extraClasses as class }
  export let rating

  $: ratings = $websocket.ratings
  $: color = colorForRating(rating, ratings)
  $: bgColor = backgroundColor(color)
</script>

<span
  class="badge badge-sm !px-1 font-normal sm:badge-md md:badge-lg sm:!px-1.5 md:font-bold {extraClasses}"
  style="color: {color}; background-color: {bgColor}; border-color: {bgColor}"
  {...$$restProps}
>
  {rating}
</span>
