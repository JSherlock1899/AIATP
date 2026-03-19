import { test, expect } from '@playwright/test'

test.describe('Authentication', () => {
  test('should show login page', async ({ page }) => {
    await page.goto('/login')
    await page.waitForLoadState('networkidle')

    // Check for login form elements
    await expect(page.locator('input[type="email"]')).toBeVisible()
    await expect(page.locator('input[type="password"]')).toBeVisible()
    await expect(page.locator('button[type="submit"]')).toBeVisible()
  })

  test('should show register link', async ({ page }) => {
    await page.goto('/login')
    await page.waitForLoadState('networkidle')

    await expect(page.locator('text=注册')).toBeVisible()
  })

  test('should navigate to register page', async ({ page }) => {
    await page.goto('/login')
    await page.waitForLoadState('networkidle')

    await page.click('text=注册')
    await page.waitForURL('**/register', { timeout: 5000 })

    // Check for registration form
    await expect(page.locator('input[type="email"]')).toBeVisible()
    await expect(page.locator('input[placeholder*="密码"]')).toBeVisible()
  })
})

test.describe('Registration', () => {
  test('should register new user', async ({ page }) => {
    const timestamp = Date.now()
    const email = `newuser_${timestamp}@test.com`
    const password = 'Test123456'
    const username = `newuser_${timestamp}`

    await page.goto('/register')
    await page.waitForLoadState('networkidle')

    // Fill form
    await page.fill('input[type="email"]', email)
    await page.fill('input[placeholder*="密码"]', password)
    await page.fill('input[placeholder*="用户"]', username)

    // Submit
    await page.click('button[type="submit"]')

    // Should redirect to projects
    await page.waitForURL('**/projects', { timeout: 10000 })

    // Should see project list
    await expect(page.locator('text=项目')).toBeVisible({ timeout: 5000 })
  })

  test('should show validation error for invalid email', async ({ page }) => {
    await page.goto('/register')
    await page.waitForLoadState('networkidle')

    await page.fill('input[type="email"]', 'invalid-email')
    await page.fill('input[placeholder*="密码"]', 'short')
    await page.fill('input[placeholder*="用户"]', 'test')

    await page.click('button[type="submit"]')

    // Should show error message
    await expect(page.locator('text=邮箱')).toBeVisible({ timeout: 3000 })
  })
})
