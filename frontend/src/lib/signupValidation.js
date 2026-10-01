export function validateSignup(email, password, confirmation) {
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) return 'Enter a valid email address.'
  if (password.length < 8 || password.length > 128 || !password.trim()) return 'Use a password of 8–128 characters that is not blank.'
  if (password !== confirmation) return 'Passwords do not match.'
  return null
}
