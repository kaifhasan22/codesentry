import { afterEach, vi } from 'vitest'
import { cleanup } from '@testing-library/react'
vi.mock('../src/components/visual/ParticleField', () => ({ ParticleField: () => null }))
afterEach(() => { cleanup(); localStorage.clear(); vi.restoreAllMocks() })
