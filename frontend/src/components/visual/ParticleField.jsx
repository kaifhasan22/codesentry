import { useEffect, useRef } from 'react'

export function ParticleField({ subtle = false }) {
  const canvasRef = useRef(null)

  useEffect(() => {
    const canvas = canvasRef.current
    const context = canvas?.getContext('2d', { alpha: true })
    if (!canvas || !context) return undefined

    let width = 600
    let pixelRatio = 1
    let frame = 0
    let rotation = 0
    let tiltX = 0
    let tiltY = 0
    let disposed = false
    const pointer = { x: -10000, y: -10000, nx: 0.5, ny: 0.5 }
    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    const count = subtle ? 850 : 1350
    const goldenAngle = Math.PI * (3 - Math.sqrt(5))
    const points = Array.from({ length: count }, (_, index) => {
      const y = 1 - 2 * (index + 0.5) / count
      const radius = Math.sqrt(1 - y * y)
      const angle = index * goldenAngle
      const x = Math.cos(angle) * radius
      const z = Math.sin(angle) * radius
      const shape = Math.pow(x ** 4 + y ** 4 + z ** 4, 0.25)
      return [x / shape, y / shape, z / shape]
    })

    const resize = () => {
      pixelRatio = Math.min(window.devicePixelRatio || 1, 2)
      width = canvas.clientWidth || 600
      canvas.width = Math.round(width * pixelRatio)
      canvas.height = Math.round(width * pixelRatio)
      if (reducedMotion) draw()
    }

    const move = (event) => {
      pointer.x = event.clientX
      pointer.y = event.clientY
      pointer.nx = event.clientX / window.innerWidth
      pointer.ny = event.clientY / window.innerHeight
    }

    const draw = () => {
      if (disposed) return
      if (!reducedMotion) {
        rotation += 0.0021
        tiltX += ((pointer.nx - 0.5) * 0.3 - tiltX) * 0.025
        tiltY += ((pointer.ny - 0.5) * 0.24 - tiltY) * 0.025
      }
      const cosA = Math.cos(rotation + tiltX)
      const sinA = Math.sin(rotation + tiltX)
      const cosB = Math.cos(tiltY)
      const sinB = Math.sin(tiltY)
      const rect = canvas.getBoundingClientRect()
      const scale = width / (rect.width || width)
      const mouseX = (pointer.x - rect.left) * scale
      const mouseY = (pointer.y - rect.top) * scale
      const spread = width * 0.365
      context.setTransform(pixelRatio, 0, 0, pixelRatio, 0, 0)
      context.clearRect(0, 0, width, width)
      context.fillStyle = getComputedStyle(document.documentElement).getPropertyValue('--particle-ink').trim() || '#f4f4f5'
      context.globalCompositeOperation = 'source-over'

      for (const [x, y, z] of points) {
        const rotatedX = x * cosA + z * sinA
        const rotatedZ = -x * sinA + z * cosA
        const tiltedY = y * cosB - rotatedZ * sinB
        const depth = y * sinB + rotatedZ * cosB
        const perspective = 2.8 / (2.8 - depth * 0.8)
        let px = width / 2 + rotatedX * spread * perspective
        let py = width / 2 + tiltedY * spread * perspective
        const dx = px - mouseX
        const dy = py - mouseY
        const distance = Math.hypot(dx, dy)
        const radius = width * 0.17
        if (!reducedMotion && distance < radius && distance > 0) {
          const push = (radius - distance) * 0.18
          px += dx / distance * push
          py += dy / distance * push
        }
        context.globalAlpha = (subtle ? 0.07 : 0.24) + (subtle ? 0.45 : 0.68) * (depth + 1) / 2
        const dot = (0.65 + 1.45 * (depth + 1) / 2) * Math.min(width / 700, 1.2)
        context.fillRect(px, py, dot, dot)
      }
      context.globalAlpha = 1
      if (!reducedMotion && !document.hidden) frame = window.requestAnimationFrame(draw)
    }

    resize()
    const observer = typeof ResizeObserver !== 'undefined' ? new ResizeObserver(resize) : null
    observer?.observe(canvas)
    window.addEventListener('mousemove', move, { passive: true })
    window.addEventListener('resize', resize, { passive: true })
    const visibility = () => {
      if (document.hidden) window.cancelAnimationFrame(frame)
      else if (!reducedMotion) frame = window.requestAnimationFrame(draw)
    }
    document.addEventListener('visibilitychange', visibility)
    if (!reducedMotion) frame = window.requestAnimationFrame(draw)

    return () => {
      disposed = true
      window.cancelAnimationFrame(frame)
      observer?.disconnect()
      window.removeEventListener('mousemove', move)
      window.removeEventListener('resize', resize)
      document.removeEventListener('visibilitychange', visibility)
    }
  }, [subtle])

  return <canvas ref={canvasRef} className={subtle ? 'particle-field particle-field-subtle' : 'particle-field'} aria-hidden="true" />
}
