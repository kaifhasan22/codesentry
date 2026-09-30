import { Link } from 'react-router-dom'
import { Header } from '../components/layout/Header'
import { ParticleField } from '../components/visual/ParticleField'

export function Home() {
  return (
    <div className="home-screen">
      <Header />
      <ParticleField />
      <main className="home-hero">
        <div className="hero-copy">
          <p className="hero-kicker">Python repository analysis</p>
          <h1>CodeSentry</h1>
          <p className="hero-subtitle">AI Code Review</p>
          <Link className="hero-link" to="/dashboard">Open workspace&nbsp; ↗</Link>
        </div>
      </main>
    </div>
  )
}
