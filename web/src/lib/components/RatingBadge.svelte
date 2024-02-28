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
  class="badge badge-sm sm:badge-md md:badge-lg {extraClasses} border-[2px] md:border-[3px]"
  style="color: {color}; background-color: {bgColor}; border-color: {color}"
  {...$$restProps}
>
  {rating}
</span>
