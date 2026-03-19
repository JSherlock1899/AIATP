import { test, expect } from '@playwright/test'

test.describe('Projects', () => {
  test('should show projects list after login', async ({ page }) => {
    // First register and login
    const timestamp = Date.now()
    const email = `e2e_${timestamp}@test.com`
    const password = 'Test123456'
    const username = `e2euser_${timestamp}`

    await page.goto('/register')
    await page.waitForLoadState('networkidle')

    // Fill and submit registration
    await page.fill('input[type="email"]', email)
    await page.fill('input[placeholder*="密码"]', password)
    await page.fill('input[placeholder*="用户"]', username)
    await page.click('button[type="submit"]')

    // Wait for redirect to projects
    await page.waitForURL('**/projects', { timeout: 10000 })
    await page.waitForLoadState('networkidle')

    // Should see projects page
    await expect(page.locator('text=项目')).toBeVisible({ timeout: 5000 })
  })

  test('should create new project', async ({ page }) => {
    // Register first
    const timestamp = Date.now()
    const email = `e2eproject_${timestamp}@test.com`
    const password = 'Test123456'
    const username = `e2eproject_${timestamp}`

    await page.goto('/register')
    await page.waitForLoadState('networkidle')
    await page.fill('input[type="email"]', email)
    await page.fill('input[placeholder*="密码"]', password)
    await page.fill('input[placeholder*="用户"]', username)
    await page.click('button[type="submit"]')
    await page.waitForURL('**/projects', { timeout: 10000 })
    await page.waitForLoadState('networkidle')

    // Click create button
    const createBtn = page.locator('button:has-text("创建"), button:has-text("新建")')
    await createBtn.click()
    await page.waitForLoadState('networkidle')

    // Fill form
    await page.fill('input[placeholder*="项目"], input[placeholder*="名称"]', `Test Project ${timestamp}`)
    await page.fill('input[placeholder*="key"], input[placeholder*="标识"]', `TEST_${timestamp}`)

    // Submit
    await page.click('button:has-text("确定"), button:has-text("创建")')
    await page.waitForLoadState('networkidle')

    // Should see new project
    await expect(page.locator(`text=Test Project ${timestamp}`)).toBeVisible({ timeout: 10000 })
  })
})
