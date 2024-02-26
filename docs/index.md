<script>
const previewTag = "preview-build"

document.addEventListener("DOMContentLoaded", async () => {
  const downloadLink = document.querySelector(`a[href="https://github.com/dtcooper/vintage-pi-tv/releases/tag/${previewTag}"]`)
  if (downloadLink) {
    const release = await(await fetch(`https://api.github.com/repos/dtcooper/vintage-pi-tv/releases/tags/${previewTag}`)).json()
    if (release.assets) {
      for (const asset of release.assets) {
        if (asset.name.endsWith(".img.xz")) {
          downloadLink.href = asset.browser_download_url
          break
        }
      }
    }
  } else {
    console.warning("Couldn't find download link to swap out preview release.")
  }
})
</script>

# Welcome

For now, as Vintage pi TV is in active development, this documentation is
a placeholder.

## Download Preview Build

Download the latest [preview release build here](https://github.com/dtcooper/vintage-pi-tv/releases/tag/preview-build).

## Configuration values

{% for name, description, optional in CONFIG_VALUES %}
* `{{ name }}` (optional {{ optional }})

{{ description }}
{% endfor %}
