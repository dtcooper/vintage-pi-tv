export const capitalize = (s) => s.charAt(0).toUpperCase() + s.slice(1)

export const isViewableBasedOnCurrentRating = (rating, currentRating, ratings) => {
  let currentRatingNum = -1
  let ratingNum = -1
  if (!rating || !currentRating) {
    return true
  }
  ratings.forEach((ratingObj, i) => {
    if (ratingObj.rating == rating) {
      ratingNum = i
    }
    if (ratingObj.rating == currentRating) {
      currentRatingNum = i
    }
  })

  if (ratingNum < 0 || currentRatingNum < 0) {
    console.error("Something when wrong decoding ratings")
    return true
  } else {
    return ratingNum <= currentRatingNum
  }
}

export const formatDuration = (secs, forceHour = false) => {
  let d = ""
  secs = Math.round(secs)
  if (secs > 3600 || forceHour) {
    d = `${Math.floor(secs / 3600)}:`
  }
  d += `${Math.floor((secs % 3600) / 60)}:`.padStart(3, "0")
  d += `${secs % 60}`.padStart(2, "0")
  return d
}

export const colorForRating = (rating, ratings) => {
  if (ratings) {
    for (const ratingObj of ratings) {
      if (ratingObj.rating === rating) {
        return ratingObj.color
      }
    }
  }
  return "#FFFFFF"
}
