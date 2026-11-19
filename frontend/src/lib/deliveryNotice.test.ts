import { describe, expect, it } from 'vitest'
import { isLateNightOrderNotice } from './deliveryNotice'

describe('isLateNightOrderNotice', () => {
  it('shows the notice from 8pm through 4:59am in Lagos time', () => {
    expect(isLateNightOrderNotice(new Date('2026-11-19T19:00:00Z'))).toBe(true)
    expect(isLateNightOrderNotice(new Date('2026-11-19T03:59:59Z'))).toBe(true)
  })

  it('hides the notice at 5am and during daytime hours', () => {
    expect(isLateNightOrderNotice(new Date('2026-11-19T04:00:00Z'))).toBe(false)
    expect(isLateNightOrderNotice(new Date('2026-11-19T18:59:59Z'))).toBe(false)
  })
})
