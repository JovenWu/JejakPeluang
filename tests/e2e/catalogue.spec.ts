import { test, expect } from '@playwright/test'

test('shows a manually approved opportunity and its source', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByRole('heading', { level: 1, name: /peluang/i })).toBeVisible()
  await expect(page.getByText('Diverifikasi moderator')).toBeVisible()
  await page.getByRole('link', { name: /uji peluang/i }).click()
  await expect(page.getByRole('link', { name: /sumber asli/i })).toHaveAttribute('href', 'https://example.org/notice')
})
