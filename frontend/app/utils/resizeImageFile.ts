/**
 * Downscales an image file in the browser before upload. A phone camera photo is routinely
 * several MB; shrinking it client-side first cuts upload time and server load dramatically.
 * The server still does its own crop-to-square/resize (see app/services/avatars.py), so this
 * only needs to get the file down to a sane size, not match that exactly — and drawing to a
 * canvas has the side effect of baking in EXIF orientation and dropping metadata, so the
 * upload is already correctly oriented with no extra work.
 */
export async function resizeImageFile(file: File, maxDimension = 512, quality = 0.85): Promise<Blob> {
  const objectUrl = URL.createObjectURL(file)
  try {
    const image = await loadImage(objectUrl)
    const scale = Math.min(1, maxDimension / Math.max(image.width, image.height))
    const targetWidth = Math.round(image.width * scale)
    const targetHeight = Math.round(image.height * scale)

    const canvas = document.createElement('canvas')
    canvas.width = targetWidth
    canvas.height = targetHeight
    const ctx = canvas.getContext('2d')
    if (!ctx) throw new Error('Canvas 2D context unavailable')
    ctx.drawImage(image, 0, 0, targetWidth, targetHeight)

    const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, 'image/jpeg', quality))
    if (!blob) throw new Error('Canvas export failed')
    return blob
  } finally {
    URL.revokeObjectURL(objectUrl)
  }
}

function loadImage(src: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image()
    img.onload = () => resolve(img)
    img.onerror = () => reject(new Error('Could not load the selected file as an image'))
    img.src = src
  })
}
