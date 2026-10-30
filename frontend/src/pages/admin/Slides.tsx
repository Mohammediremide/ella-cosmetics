import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowDown, ArrowUp, Film, Pencil, Plus, Trash2, Upload } from 'lucide-react'
import { api, ApiError, assetUrl, fieldError } from '../../lib/api'
import { useToast } from '../../lib/toast'
import type { Slide } from '../../lib/types'
import { Field, Modal, Skeleton } from '../../components/ui'

const MAX_MB = 30
const isVideo = (f: File) => f.type.startsWith('video/')

function Thumb({ s, className = '' }: { s: Slide; className?: string }) {
  return s.media_type === 'video' && s.video
    ? <video src={assetUrl(s.video)} muted playsInline preload="metadata" className={`h-full w-full object-cover ${className}`} aria-hidden />
    : <img src={assetUrl(s.image)} alt="" className={`h-full w-full object-cover ${className}`} />
}

function SlideForm({ slide, onClose }: { slide: Slide | null; onClose: () => void }) {
  const qc = useQueryClient(), toast = useToast()
  const [file, setFile] = useState<File | null>(null)
  const [f, setF] = useState({ title: slide?.title ?? '', subtitle: slide?.subtitle ?? '', button_label: slide?.button_label ?? '', link_url: slide?.link_url ?? '', is_active: slide?.is_active ?? true })
  const [err, setErr] = useState<unknown>(null)
  const [sizeErr, setSizeErr] = useState('')
  const save = useMutation({
    mutationFn: () => {
      const form = new FormData()
      Object.entries(f).forEach(([k, v]) => form.append(k, String(v)))
      if (file) form.append(isVideo(file) ? 'video' : 'image', file)
      return api<Slide>(slide ? `/admin/slides/${slide.id}/` : '/admin/slides/', { method: slide ? 'PATCH' : 'POST', form })
    },
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['admin', 'slides'] }); qc.invalidateQueries({ queryKey: ['slides'] }); toast(slide ? 'Slide updated' : 'Slide added to the homepage'); onClose() },
    onError: (e) => { setErr(e); toast(e instanceof ApiError ? 'Please fix the highlighted fields' : 'Upload failed. Check your connection and try again.', 'error') },
  })
  const pick = (x?: File) => {
    setSizeErr('')
    if (!x) return
    if (x.size > MAX_MB * 1024 * 1024) { setSizeErr(`That file is ${(x.size / 1048576).toFixed(0)} MB. The limit is ${MAX_MB} MB: compress it or trim it to under ~20 seconds.`); return }
    setFile(x)
  }
  const previewUrl = file ? URL.createObjectURL(file) : null
  const mediaErr = fieldError(err, 'video') ?? fieldError(err, 'image') ?? sizeErr
  return (
    <form noValidate onSubmit={(e) => { e.preventDefault(); setErr(null); save.mutate() }} className="space-y-4">
      <div>
        <p className="label">Video or image {slide ? '(leave empty to keep the current one)' : ''}</p>
        <div className="flex items-center gap-3">
          <div className="h-20 w-32 shrink-0 overflow-hidden rounded-brand bg-blush">
            {previewUrl ? (file && isVideo(file) ? <video src={previewUrl} muted playsInline className="h-full w-full object-cover" /> : <img src={previewUrl} alt="" className="h-full w-full object-cover" />)
              : slide ? <Thumb s={slide} /> : <div className="flex h-full items-center justify-center text-burgundy/40"><Film aria-hidden /></div>}
          </div>
          <label className="btn-outline cursor-pointer"><Upload size={16} aria-hidden /> {file || slide ? 'Change file' : 'Choose file'}
            <input type="file" accept="video/mp4,video/webm,image/jpeg,image/png,image/webp" className="sr-only" onChange={(e) => { pick(e.target.files?.[0]); e.target.value = '' }} /></label>
        </div>
        {file && <p className="mt-1 text-xs text-muted">{file.name} · {(file.size / 1048576).toFixed(1)} MB</p>}
        {mediaErr && <p className="field-error" role="alert">{mediaErr}</p>}
        <p className="mt-1 text-xs text-muted">MP4 or WebM video up to {MAX_MB} MB (short clips of 10–20 seconds work best), or a JPEG/PNG/WebP image. Videos play without sound.</p>
      </div>
      <Field label="Headline (optional)" htmlFor="st" error={fieldError(err, 'title')}><input id="st" className="input" maxLength={80} value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} placeholder="e.g. Discover your kind of beautiful" /></Field>
      <Field label="Sub-text (optional)" htmlFor="ss" error={fieldError(err, 'subtitle')}><input id="ss" className="input" maxLength={160} value={f.subtitle} onChange={(e) => setF({ ...f, subtitle: e.target.value })} /></Field>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Button text (optional)" htmlFor="sb" error={fieldError(err, 'button_label')}><input id="sb" className="input" maxLength={40} value={f.button_label} onChange={(e) => setF({ ...f, button_label: e.target.value })} placeholder="Shop now" /></Field>
        <Field label="Button link" htmlFor="sl" error={fieldError(err, 'link_url')}><input id="sl" className="input" value={f.link_url} onChange={(e) => setF({ ...f, link_url: e.target.value })} placeholder="/shop?category=makeup" /></Field>
      </div>
      <label className="flex min-h-[44px] items-center gap-2 text-sm"><input type="checkbox" className="h-4 w-4 accent-burgundy" checked={f.is_active} onChange={(e) => setF({ ...f, is_active: e.target.checked })} /> Show on the homepage</label>
      <div className="flex items-center justify-end gap-3">
        {save.isPending && <span className="text-xs text-muted" role="status">Uploading… large videos can take a minute.</span>}
        <button type="button" className="btn-ghost" onClick={onClose} disabled={save.isPending}>Cancel</button>
        <button className="btn-primary" disabled={save.isPending || (!slide && !file)}>{save.isPending ? 'Saving…' : slide ? 'Save changes' : 'Add slide'}</button>
      </div>
    </form>
  )
}

export default function Slides() {
  const qc = useQueryClient(), toast = useToast()
  const [editing, setEditing] = useState<Slide | 'new' | null>(null)
  const [del, setDel] = useState<Slide | null>(null)
  const { data = [], isLoading } = useQuery({ queryKey: ['admin', 'slides'], queryFn: () => api<Slide[]>('/admin/slides/') })
  const done = () => { qc.invalidateQueries({ queryKey: ['admin', 'slides'] }); qc.invalidateQueries({ queryKey: ['slides'] }) }
  const fail = (e: unknown) => toast(e instanceof ApiError ? e.message : 'Something went wrong', 'error')
  const toggle = useMutation({ mutationFn: (s: Slide) => api(`/admin/slides/${s.id}/`, { method: 'PATCH', body: { is_active: !s.is_active } }), onSuccess: done, onError: fail })
  const reorder = useMutation({ mutationFn: (ids: number[]) => api('/admin/slides/reorder/', { method: 'POST', body: { ids } }), onSuccess: done, onError: fail })
  const remove = useMutation({ mutationFn: (s: Slide) => api(`/admin/slides/${s.id}/`, { method: 'DELETE' }), onSuccess: () => { done(); toast('Slide deleted'); setDel(null) }, onError: (e) => { fail(e); setDel(null) } })
  const move = (i: number, d: number) => { const ids = data.map((s) => s.id); [ids[i], ids[i + d]] = [ids[i + d], ids[i]]; reorder.mutate(ids) }

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div><h1 className="text-4xl">Homepage Slideshow</h1><p className="mt-1 max-w-xl text-sm text-muted">Upload videos or photos that play as a slideshow at the top of your homepage. Each video plays once, then the next slide starts. With no slides, the homepage shows the default Ella Cosmetics banner.</p></div>
        <button className="btn-primary" onClick={() => setEditing('new')} disabled={data.length >= 10}><Plus size={18} aria-hidden /> Add slide</button>
      </div>
      <ul className="mt-6 space-y-3">
        {isLoading ? <Skeleton className="h-32" /> : data.map((s, i) => (
          <li key={s.id} className={`card flex flex-wrap items-center gap-3 p-3 sm:gap-4 sm:p-4 ${s.is_active ? '' : 'opacity-70'}`}>
            <div className="flex flex-col">
              <button className="btn-ghost min-h-9 px-2" aria-label={`Move slide ${i + 1} up`} disabled={i === 0 || reorder.isPending} onClick={() => move(i, -1)}><ArrowUp size={16} /></button>
              <button className="btn-ghost min-h-9 px-2" aria-label={`Move slide ${i + 1} down`} disabled={i === data.length - 1 || reorder.isPending} onClick={() => move(i, 1)}><ArrowDown size={16} /></button>
            </div>
            <div className="relative h-20 w-32 shrink-0 overflow-hidden rounded-brand bg-blush"><Thumb s={s} />{s.media_type === 'video' && <span className="absolute bottom-1 left-1 rounded bg-charcoal/80 px-1.5 py-0.5 text-[10px] text-white">VIDEO</span>}</div>
            <div className="min-w-0 flex-1 basis-40">
              <p className="font-medium">{s.title || <span className="text-muted">No headline</span>} {!s.is_active && <span className="ml-1 rounded-full bg-stone-100 px-2 py-0.5 text-xs text-stone-700">Hidden</span>}</p>
              {s.subtitle && <p className="truncate text-sm text-muted">{s.subtitle}</p>}
              {s.button_label && <p className="text-xs text-muted">Button: “{s.button_label}” → {s.link_url}</p>}
            </div>
            <div className="flex items-center gap-1">
              <button role="switch" aria-checked={!!s.is_active} aria-label={`Slide ${i + 1} visible`} onClick={() => toggle.mutate(s)} disabled={toggle.isPending} className={`relative h-7 w-12 rounded-full transition-colors ${s.is_active ? 'bg-burgundy' : 'bg-taupe/60'}`}><span className={`absolute top-1 h-5 w-5 rounded-full bg-white transition-all ${s.is_active ? 'left-6' : 'left-1'}`} /></button>
              <button className="btn-ghost px-3" aria-label={`Edit slide ${i + 1}`} onClick={() => setEditing(s)}><Pencil size={16} /></button>
              <button className="btn-ghost px-3" aria-label={`Delete slide ${i + 1}`} onClick={() => setDel(s)}><Trash2 size={16} /></button>
            </div>
          </li>))}
        {!isLoading && !data.length && <li className="card p-8 text-center text-sm text-muted">No slides yet. Add a video or photo to replace the default banner.</li>}
      </ul>
      <Modal open={!!editing} title={editing === 'new' ? 'Add slide' : 'Edit slide'} onClose={() => setEditing(null)}>{editing && <SlideForm key={editing === 'new' ? 'new' : editing.id} slide={editing === 'new' ? null : editing} onClose={() => setEditing(null)} />}</Modal>
      <Modal open={!!del} title="Delete slide?" onClose={() => setDel(null)}>
        <p className="text-sm">This removes the slide and its uploaded file permanently. To hide it temporarily, use the switch instead.</p>
        <div className="mt-5 flex justify-end gap-3"><button className="btn-ghost" onClick={() => setDel(null)}>Cancel</button><button className="btn-primary" disabled={remove.isPending} onClick={() => del && remove.mutate(del)}>Delete</button></div>
      </Modal>
    </div>
  )
}
