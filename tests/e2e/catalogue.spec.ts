import { test, expect } from '@playwright/test'

test('landing page introduces the product and links categories', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByRole('heading', { level: 1, name: /cek dulu/i })).toBeVisible()
  await expect(page.getByRole('link', { name: /cek sekarang/i })).toHaveAttribute('href', '/cek')
  await expect(page.getByRole('link', { name: /beasiswa/i }).first()).toHaveAttribute(
    'href', '/peluang?category=scholarship')
})

test('shows a manually approved opportunity and its source', async ({ page }) => {
  await page.goto('/peluang')
  await expect(page.getByRole('heading', { level: 1, name: /peluang/i })).toBeVisible()
  await expect(page.getByText('terverifikasi').first()).toBeVisible()
  await page.getByRole('link', { name: /uji peluang/i }).click()
  await expect(page.getByRole('link', { name: /sumber resmi/i })).toHaveAttribute(
    'href', 'https://example.org/notice')
})

test('check form renders and validates empty input', async ({ page }) => {
  await page.goto('/cek')
  await expect(page.getByRole('heading', { level: 1, name: /cek info/i })).toBeVisible()
  await page.getByRole('button', { name: /cek sekarang/i }).click()
  await expect(page.getByText(/isi tautan atau unggah/i)).toBeVisible()
})
