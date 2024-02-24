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
