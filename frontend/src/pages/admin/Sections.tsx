import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowDown, ArrowUp, ImagePlus, Pencil, Plus, Trash2 } from 'lucide-react'
import { api, ApiError, fieldError } from '../../lib/api'
import { useToast } from '../../lib/toast'
import type { Category } from '../../lib/types'
import { Field, Img, Modal, Skeleton } from '../../components/ui'

function SectionForm({ section, onClose }: { section: Category | null; onClose: () => void }) {
  const qc = useQueryClient(), toast = useToast()
  const [name, setName] = useState(section?.name ?? '')
  const [description, setDescription] = useState(section?.description ?? '')
  const [file, setFile] = useState<File | null>(null)
  const [active, setActive] = useState(section?.is_active ?? true)
  const [err, setErr] = useState<unknown>(null)
  const save = useMutation({
    mutationFn: async () => {
      const f = new FormData(); f.append('name', name); f.append('description', description); f.append('is_active', String(active)); if (file) f.append('image', file)
      return api<Category>(section ? `/admin/categories/${section.id}/` : '/admin/categories/', { method: section ? 'PATCH' : 'POST', form: f })
    },
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['admin', 'categories'] }); qc.invalidateQueries({ queryKey: ['categories'] }); qc.invalidateQueries({ queryKey: ['products'] }); toast(section ? 'Section updated' : 'Section created'); onClose() },
    onError: (e) => { setErr(e); toast(e instanceof ApiError ? 'Please fix the highlighted fields' : 'Save failed', 'error') },
  })
  const preview = file ? URL.createObjectURL(file) : section?.image
  return (
    <form noValidate onSubmit={(e) => { e.preventDefault(); setErr(null); save.mutate() }} className="space-y-4">
      <Field label="Section name" htmlFor="sn" error={fieldError(err, 'name')}><input id="sn" className="input" maxLength={80} value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Skincare" autoFocus /></Field>
      <Field label="Description (optional)" htmlFor="sd" error={fieldError(err, 'description')}><textarea id="sd" rows={2} maxLength={300} className="input py-3" value={description} onChange={(e) => setDescription(e.target.value)} placeholder="A short line shown on the section page" /></Field>
      <div>
        <p className="label">Cover image (optional)</p>
        <div className="flex items-center gap-3">
          <div className="w-20 overflow-hidden rounded-brand"><Img src={preview} alt="" ratio="aspect-square" /></div>
          <label className="btn-outline cursor-pointer"><ImagePlus size={16} aria-hidden /> {preview ? 'Change image' : 'Upload image'}<input type="file" accept="image/jpeg,image/png,image/webp" className="sr-only" onChange={(e) => setFile(e.target.files?.[0] ?? null)} /></label>
        </div>
        {fieldError(err, 'image') && <p className="field-error" role="alert">{fieldError(err, 'image')}</p>}
        <p className="mt-1 text-xs text-muted">JPEG, PNG or WebP, up to 5 MB.</p>
      </div>
      <label className="flex min-h-[44px] items-center gap-2 text-sm"><input type="checkbox" className="h-4 w-4 accent-burgundy" checked={active} onChange={(e) => setActive(e.target.checked)} /> Active (visible to customers)</label>
      <div className="flex justify-end gap-3"><button type="button" className="btn-ghost" onClick={onClose}>Cancel</button><button className="btn-primary" disabled={save.isPending}>{save.isPending ? 'Saving…' : section ? 'Save changes' : 'Create section'}</button></div>
    </form>
  )
}

export default function Sections() {
  const qc = useQueryClient(), toast = useToast()
  const [editing, setEditing] = useState<Category | 'new' | null>(null)
  const [del, setDel] = useState<Category | null>(null)
  const { data = [], isLoading } = useQuery({ queryKey: ['admin', 'categories'], queryFn: () => api<Category[]>('/admin/categories/') })
  const done = () => { qc.invalidateQueries({ queryKey: ['admin', 'categories'] }); qc.invalidateQueries({ queryKey: ['categories'] }); qc.invalidateQueries({ queryKey: ['products'] }) }
  const fail = (e: unknown) => toast(e instanceof ApiError ? e.message : 'Something went wrong', 'error')
  const toggle = useMutation({ mutationFn: (c: Category) => api(`/admin/categories/${c.id}/`, { method: 'PATCH', body: { is_active: !c.is_active } }), onSuccess: (_d, c) => { done(); toast(c.is_active ? `${c.name} hidden from customers` : `${c.name} is now visible`) }, onError: fail })
  const reorder = useMutation({ mutationFn: (ids: number[]) => api('/admin/categories/reorder/', { method: 'POST', body: { ids } }), onSuccess: done, onError: fail })
  const remove = useMutation({ mutationFn: (c: Category) => api(`/admin/categories/${c.id}/`, { method: 'DELETE' }), onSuccess: () => { done(); toast('Section deleted'); setDel(null) }, onError: (e) => { fail(e); setDel(null) } })
  const move = (i: number, d: number) => { const ids = data.map((c) => c.id); [ids[i], ids[i + d]] = [ids[i + d], ids[i]]; reorder.mutate(ids) }

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3"><div><h1 className="text-4xl">Manage Sections</h1><p className="mt-1 text-sm text-muted">Sections group your products in the shop menu and on the homepage. New sections appear automatically in the product form.</p></div>
        <button className="btn-primary" onClick={() => setEditing('new')}><Plus size={18} aria-hidden /> New section</button></div>
      <ul className="mt-6 space-y-3">
        {isLoading ? <Skeleton className="h-40" /> : data.map((c, i) => (
          <li key={c.id} className={`card flex flex-wrap items-center gap-3 p-3 sm:gap-4 sm:p-4 ${c.is_active ? '' : 'opacity-70'}`}>
            <div className="flex flex-col"><button className="btn-ghost min-h-9 px-2" aria-label={`Move ${c.name} up`} disabled={i === 0 || reorder.isPending} onClick={() => move(i, -1)}><ArrowUp size={16} /></button>
              <button className="btn-ghost min-h-9 px-2" aria-label={`Move ${c.name} down`} disabled={i === data.length - 1 || reorder.isPending} onClick={() => move(i, 1)}><ArrowDown size={16} /></button></div>
            <div className="w-16 shrink-0 overflow-hidden rounded-brand"><Img src={c.image} alt="" ratio="aspect-square" /></div>
            <div className="min-w-0 flex-1 basis-40">
              <p className="font-medium">{c.name} {!c.is_active && <span className="ml-1 rounded-full bg-stone-100 px-2 py-0.5 text-xs text-stone-700">Hidden</span>}</p>
              {c.description && <p className="truncate text-sm text-muted">{c.description}</p>}
              <p className="text-xs text-muted">{c.product_count} {c.product_count === 1 ? 'product' : 'products'}{(c.total_products ?? 0) > (c.product_count ?? 0) && ` (+${(c.total_products ?? 0) - (c.product_count ?? 0)} archived)`}</p>
            </div>
            <div className="flex flex-wrap items-center gap-1">
              <button role="switch" aria-checked={!!c.is_active} aria-label={`${c.name} active`} onClick={() => toggle.mutate(c)} disabled={toggle.isPending}
                className={`relative h-7 w-12 rounded-full transition-colors ${c.is_active ? 'bg-burgundy' : 'bg-taupe/60'}`}><span className={`absolute top-1 h-5 w-5 rounded-full bg-white transition-all ${c.is_active ? 'left-6' : 'left-1'}`} /></button>
              <button className="btn-ghost px-3" aria-label={`Edit ${c.name}`} onClick={() => setEditing(c)}><Pencil size={16} /></button>
              <button className="btn-ghost px-3" aria-label={`Delete ${c.name}`} title={c.total_products ? 'Sections with products can only be hidden' : 'Delete'} disabled={!!c.total_products} onClick={() => setDel(c)}><Trash2 size={16} /></button>
            </div>
          </li>))}
        {!isLoading && !data.length && <li className="card p-8 text-center text-sm text-muted">No sections yet. Create one so you can add products.</li>}
      </ul>
      <p className="mt-4 text-xs text-muted">Hiding a section removes it and its products from the shop, but nothing is deleted and past orders are untouched. Sections that have products (even archived ones) can’t be deleted.</p>
      <Modal open={!!editing} title={editing === 'new' ? 'New section' : 'Edit section'} onClose={() => setEditing(null)}>{editing && <SectionForm key={editing === 'new' ? 'new' : editing.id} section={editing === 'new' ? null : editing} onClose={() => setEditing(null)} />}</Modal>
      <Modal open={!!del} title="Delete section?" onClose={() => setDel(null)}>
        <p className="text-sm">“{del?.name}” has no products and will be removed permanently.</p>
        <div className="mt-5 flex justify-end gap-3"><button className="btn-ghost" onClick={() => setDel(null)}>Cancel</button><button className="btn-primary" disabled={remove.isPending} onClick={() => del && remove.mutate(del)}>Delete</button></div>
      </Modal>
    </div>
  )
}
