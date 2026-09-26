import { render, screen } from '@testing-library/react'
import '@testing-library/jest-dom/vitest'
import { expect, it } from 'vitest'
import { OpportunityCard } from './opportunity-card'

it('shows issuer, checked source and moderator status in text', () => {
  render(<OpportunityCard opportunity={{
    slug: 'uji-peluang', title: 'Uji Peluang', category: 'scholarship',
    issuer_name: 'Example University', deadline: null,
    checked_at: '2026-09-01T00:00:00Z', verified_at: '2026-09-01T00:00:00Z',
    trust_basis: 'public_source', status: 'published',
    source_url: 'https://example.org/notice', ai_source_match: false,
  }} />)
  expect(screen.getByText('Example University')).toBeInTheDocument()
  expect(screen.getByText('Diverifikasi moderator')).toBeInTheDocument()
  expect(screen.getByRole('link', { name: /sumber asli/i })).toHaveAttribute('href', 'https://example.org/notice')
})
