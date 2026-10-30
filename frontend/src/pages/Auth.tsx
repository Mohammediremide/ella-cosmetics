import { useState } from 'react'
import { Link, Navigate, useLocation, useNavigate, useSearchParams } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Eye, EyeOff } from 'lucide-react'
import { ApiError, fieldError } from '../lib/api'
import { useAuth } from '../lib/auth'
import { Field } from '../components/ui'

const loginSchema = z.object({ email: z.string().email('Enter a valid email'), password: z.string().min(1, 'Enter your password') })
const regSchema = z.object({ name: z.string().trim().min(2, 'Enter your name'), email: z.string().email('Enter a valid email'), password: z.string().min(8, 'Use at least 8 characters'), phone: z.string().optional() })

function Password({ id, reg, autoComplete }: { id: string; reg: any; autoComplete: string }) {
  const [show, setShow] = useState(false)
  return (
    <div className="relative">
      <input id={id} type={show ? 'text' : 'password'} autoComplete={autoComplete} className="input pr-12" {...reg} />
      <button type="button" className="absolute inset-y-0 right-0 px-3 text-muted" aria-label={show ? 'Hide password' : 'Show password'} onClick={() => setShow((v) => !v)}>{show ? <EyeOff size={18} /> : <Eye size={18} />}</button>
    </div>
  )
}

export default function Auth({ mode }: { mode: 'login' | 'register' }) {
  const { user, login, register: signUp } = useAuth()
  const [sp] = useSearchParams()
  const nav = useNavigate()
  const next = sp.get('next') || '/account'
  const [err, setErr] = useState<unknown>(null)
  const isLogin = mode === 'login'
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<any>({ resolver: zodResolver(isLogin ? loginSchema : regSchema) })
  useLocation()
  if (user) return <Navigate to={user.is_staff && next === '/account' ? '/admin' : next} replace />
  const submit = handleSubmit(async (d) => {
    setErr(null)
    try { const u = isLogin ? await login(d.email, d.password) : await signUp(d); nav(u.is_staff && next === '/account' ? '/admin' : next, { replace: true }) } catch (e) { setErr(e) }
  })
  const generic = err instanceof ApiError && !Object.keys(err.fields).some((k) => ['email', 'password', 'name', 'phone'].includes(k)) ? err.message : null
  return (
    <div className="container-x flex justify-center py-12">
      <form onSubmit={submit} noValidate className="card w-full max-w-md space-y-4 p-7">
        <h1 className="text-3xl">{isLogin ? 'Welcome back' : 'Create your account'}</h1>
        {generic && <p role="alert" className="rounded-brand bg-red-50 p-3 text-sm text-red-800">{generic}</p>}
        {!isLogin && <Field label="Full name" htmlFor="name" error={(errors.name?.message as string) ?? fieldError(err, 'name')}><input id="name" className="input" autoComplete="name" {...register('name')} /></Field>}
        <Field label="Email" htmlFor="email" error={(errors.email?.message as string) ?? fieldError(err, 'email')}><input id="email" type="email" className="input" autoComplete="email" {...register('email')} /></Field>
        <Field label="Password" htmlFor="pw" error={(errors.password?.message as string) ?? fieldError(err, 'password')}><Password id="pw" autoComplete={isLogin ? 'current-password' : 'new-password'} reg={register('password')} /></Field>
        {isLogin && <p className="-mt-2 text-right text-sm"><Link className="text-burgundy underline" to="/forgot-password">Forgot password?</Link></p>}
        <button className="btn-primary w-full" disabled={isSubmitting}>{isSubmitting ? 'Please wait…' : isLogin ? 'Sign in' : 'Create account'}</button>
        <p className="text-center text-sm text-muted">{isLogin ? 'New here?' : 'Already have an account?'} <Link className="text-burgundy underline" to={`${isLogin ? '/register' : '/login'}${sp.get('next') ? `?next=${sp.get('next')}` : ''}`}>{isLogin ? 'Create an account' : 'Sign in'}</Link></p>
      </form>
    </div>
  )
}
