// Port of the approved intro's irregular pixel diffusion. No network or animation dependency.
const clamp = (n: number) => Math.max(0, Math.min(1, n));
type Pixel = { offset: number; alpha: number; reveal: number; red: number; green: number; blue: number };
export function animateInk(word: HTMLCanvasElement, emblem: HTMLCanvasElement, url: string, reduced: boolean) {
  const context = word.getContext('2d');
  const emblemContext = emblem.getContext('2d');
  if (!context || !emblemContext) return;
  let disposed = false;
  let frame = 0;
  const wordPixels: Pixel[] = [];
  const logoPixels: Pixel[] = [];
  const mask = document.createElement('canvas');
  mask.width = word.width; mask.height = word.height;
  const ink = mask.getContext('2d', { willReadFrequently: true });
  if (!ink) return;
  ink.scale(2, 2); ink.textAlign = 'center'; ink.font = "600 88px 'Century Gothic', 'Segoe UI', sans-serif"; ink.fillStyle = '#f1eee6';
  const positions = [52, 151, 257, 365, 467, 563, 661, 759, 858, 958];
  Array.from('FLOWTRACER').forEach((letter, index) => {
    ink.clearRect(0, 0, 1012, 124); ink.fillText(letter, positions[index], 91);
    const data = ink.getImageData(0, 0, word.width, word.height).data;
    for (let py = 0; py < word.height; py++) for (let px = Math.max(0, (positions[index] - 60) * 2); px < Math.min(word.width, (positions[index] + 60) * 2); px++) {
      const offset = (py * word.width + px) * 4;
      if (data[offset + 3] < 8) continue;
      const x = px / 2, y = py / 2;
      const spread = Math.min(Math.hypot(x - positions[index] + 19, y - 39), Math.hypot(x - positions[index] - 17, y - 78)) / 96;
      const wave = .1 * Math.sin(x * .117 + y * .068 + index * 1.7) + .07 * Math.sin(x * .047 - y * .159 + index * 2.3) + .035 * Math.sin(x * .36 + y * .27);
      wordPixels.push({ offset, alpha: data[offset + 3], reveal: .32 + index * .33 + clamp(spread * .79 + wave), red: 241, green: 238, blue: 230 });
    }
  });
  const wordImage = context.createImageData(word.width, word.height);
  const logoImage = emblemContext.createImageData(emblem.width, emblem.height);
  const render = (pixels: Pixel[], image: ImageData, target: CanvasRenderingContext2D, time: number) => {
    for (const pixel of pixels) { const { offset } = pixel; image.data[offset] = pixel.red; image.data[offset + 1] = pixel.green; image.data[offset + 2] = pixel.blue; image.data[offset + 3] = Math.round(pixel.alpha * clamp((time - pixel.reveal) / .23)); }
    target.putImageData(image, 0, 0);
  };
  const image = new Image();
  image.onload = () => {
    if (disposed) return;
    const source = document.createElement('canvas'); source.width = image.naturalWidth; source.height = image.naturalHeight;
    const sourceInk = source.getContext('2d', { willReadFrequently: true }); if (!sourceInk) return;
    sourceInk.drawImage(image, 0, 0);
    const original = sourceInk.getImageData(0, 0, source.width, source.height);
    // Preserve the two approved removals, including their original connected-component bounds.
    for (const [sx, sy, minX, maxX, minY, maxY] of [[230,490,180,365,452,555], [1000,800,905,1095,747,850]]) {
      const scaleX = source.width / 1254, scaleY = source.height / 1254;
      const queue = [Math.round(sy * scaleY) * source.width + Math.round(sx * scaleX)];
      const visited = new Uint8Array(source.width * source.height);
      for (let head = 0; head < queue.length; head++) {
        const i = queue[head]; if (visited[i] || original.data[i * 4 + 3] < 8) continue;
        visited[i] = 1; original.data[i * 4 + 3] = 0;
        const x = i % source.width, y = Math.floor(i / source.width);
        for (let dy = -1; dy <= 1; dy++) for (let dx = -1; dx <= 1; dx++) { const nx = x + dx, ny = y + dy; if (nx >= minX * scaleX && nx <= maxX * scaleX && ny >= minY * scaleY && ny <= maxY * scaleY) queue.push(ny * source.width + nx); }
      }
    }
    sourceInk.putImageData(original, 0, 0);
    const logo = document.createElement('canvas'); logo.width = 512; logo.height = 512;
    const ctx = logo.getContext('2d', { willReadFrequently: true }); if (!ctx) return;
    ctx.drawImage(source, 0, 0, 512, 512); const data = ctx.getImageData(0, 0, 512, 512).data;
    for (let y = 0; y < 512; y++) for (let x = 0; x < 512; x++) {
      const offset = (y * 512 + x) * 4; if (data[offset + 3] < 8) continue;
      const spread = Math.min(Math.hypot(x - 256, y - 256) * .92, Math.hypot(x - 185, y - 167) * 1.1, Math.hypot(x - 329, y - 343) * 1.1) / 235;
      const wave = .13 * Math.sin(x * .051 + y * .039) + .085 * Math.sin(x * .113 - y * .071) + .045 * Math.sin(x * .31 + y * .22);
      logoPixels.push({ offset, alpha: data[offset + 3], red: data[offset], green: data[offset + 1], blue: data[offset + 2], reveal: 4.56 + Math.pow(clamp(spread * 1.25 + wave), 1.35) * 1.42 });
    }
    const origin = performance.now();
    const draw = (now: number) => {
      if (disposed) return;
      const seconds = reduced ? 7 : (now - origin) / 1000;
      render(wordPixels, wordImage, context, seconds); render(logoPixels, logoImage, emblemContext, seconds);
      if (seconds < 6.3) frame = requestAnimationFrame(draw);
      else word.dataset.complete = 'true';
    };
    frame = requestAnimationFrame(draw);
  };
  image.onerror = () => { if (!disposed) render(wordPixels, wordImage, context, 7); };
  image.src = url;
  return () => { disposed = true; cancelAnimationFrame(frame); image.onload = null; image.onerror = null; };
}
