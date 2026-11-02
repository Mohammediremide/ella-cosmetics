// Production-build guard: fail on Vercel if the API proxy was never pointed at the real backend.
import fs from 'fs'
if (process.env.VERCEL) {
  const file = new URL('../vercel.json', import.meta.url)
  if (!fs.existsSync(file)) { console.error('\nDeploy blocked: frontend/vercel.json is missing. Copy frontend/vercel.example.json to frontend/vercel.json and put your Render host in it.\n'); process.exit(1) }
  const cfg = fs.readFileSync(file, 'utf8')
  if (cfg.includes('YOUR-BACKEND-HOST') && !process.env.VITE_API_BASE_URL) {
    console.error('\nDeploy blocked: edit frontend/vercel.json and replace YOUR-BACKEND-HOST with your backend host\n(or set VITE_API_BASE_URL to call the API host directly). See README → Deployment.\n')
    process.exit(1)
  }
}
if (/localhost|127\.0\.0\.1/.test(process.env.VITE_API_BASE_URL ?? '')) console.warn('Warning: VITE_API_BASE_URL points at localhost; production builds should not.')
