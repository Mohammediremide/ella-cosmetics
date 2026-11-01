import { useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { api, ApiError, fieldError } from '../lib/api'
import { useToast } from '../lib/toast'
import { Field } from '../components/ui'
import { usePublicSettings } from '../components/Layout'

export function ForgotPassword() {
  const { data: store } = usePublicSettings()
  const [sent, setSent] = useState(false)
  const [err, setErr] = useState('')
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<{ email: string }>({ resolver: zodResolver(z.object({ email: z.string().email('Enter a valid email') })) })
  const submit = handleSubmit(async (d) => {
    setErr('')
    try { await api('/auth/password-reset/', { method: 'POST', body: d }); setSent(true) } catch (e) { setErr(e instanceof ApiError ? e.message : 'Something went wrong') }
  })
  if (store && !store.password_reset_enabled) return (
    <div className="container-x flex justify-center py-12"><div className="card w-full max-w-md space-y-4 p-7">
      <h1 className="text-3xl">Forgot your password?</h1>
      <p className="text-sm">Online password reset isn’t available right now. Please contact us{store.whatsapp_number ? <> on <a className="font-medium text-burgundy underline" href={`https://wa.me/${store.whatsapp_number}`} target="_blank" rel="noreferrer">WhatsApp</a></> : ''} and we’ll help you get back into your account.</p>
      <Link className="btn-outline w-full" to="/login">Back to sign in</Link></div></div>
  )
  return (
    <div className="container-x flex justify-center py-12">
      <form onSubmit={submit} noValidate className="card w-full max-w-md space-y-4 p-7">
        <h1 className="text-3xl">Forgot your password?</h1>
        {sent ? <p role="status" className="rounded-brand bg-blush/50 p-4 text-sm">If an account exists for that email, we’ve sent a link to choose a new password. It expires in 1 hour. Check your spam folder if you don’t see it.</p> : <>
          <p className="text-sm text-muted">Enter your email and we’ll send you a link to reset it.</p>
          {err && <p role="alert" className="rounded-brand bg-red-50 p-3 text-sm text-red-800">{err}</p>}
          <Field label="Email" htmlFor="fe" error={errors.email?.message}><input id="fe" type="email" autoComplete="email" className="input" {...register('email')} /></Field>
          <button className="btn-primary w-full" disabled={isSubmitting}>{isSubmitting ? 'Sending…' : 'Send reset link'}</button></>}
        <p className="text-center text-sm"><Link className="text-burgundy underline" to="/login">Back to sign in</Link></p>
      </form>
    </div>
  )
}

const schema = z.object({ password: z.string().min(8, 'Use at least 8 characters'), confirm: z.string() }).refine((d) => d.password === d.confirm, { path: ['confirm'], message: 'Passwords don’t match' })

export function ResetPassword() {
  const [sp] = useSearchParams()
  const nav = useNavigate(), toast = useToast()
  const [err, setErr] = useState<unknown>(null)
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<z.infer<typeof schema>>({ resolver: zodResolver(schema) })
  const uid = sp.get('uid'), token = sp.get('token')
  const submit = handleSubmit(async (d) => {
    setErr(null)
    try { await api('/auth/password-reset/confirm/', { method: 'POST', body: { uid, token, password: d.password } }); toast('Password updated. Please sign in.'); nav('/login', { replace: true }) } catch (e) { setErr(e) }
  })
  if (!uid || !token) return <div className="container-x py-16 text-center"><p>This reset link is incomplete.</p><Link className="btn-primary mt-4" to="/forgot-password">Request a new link</Link></div>
  const bad = err instanceof ApiError && err.code === 'invalid_token'
  return (
    <div className="container-x flex justify-center py-12">
      <form onSubmit={submit} noValidate className="card w-full max-w-md space-y-4 p-7">
        <h1 className="text-3xl">Choose a new password</h1>
        {bad && <p role="alert" className="rounded-brand bg-red-50 p-3 text-sm text-red-800">{(err as ApiError).message} <Link className="underline" to="/forgot-password">Request a new link</Link></p>}
        <Field label="New password" htmlFor="np" error={errors.password?.message ?? fieldError(err, 'password')}><input id="np" type="password" autoComplete="new-password" className="input" {...register('password')} /></Field>
        <Field label="Confirm new password" htmlFor="cp" error={errors.confirm?.message}><input id="cp" type="password" autoComplete="new-password" className="input" {...register('confirm')} /></Field>
        <button className="btn-primary w-full" disabled={isSubmitting}>{isSubmitting ? 'Saving…' : 'Update password'}</button>
      </form>
    </div>
  )
}
