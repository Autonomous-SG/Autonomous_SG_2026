import { useEffect, useId, useRef, useState } from 'react'
import { airports } from '../utils/scenarioOptions'

export default function AirportPicker({ label, value, onChange }) {
  const id = useId()
  const rootRef = useRef(null)
  const listRef = useRef(null)
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState(null)
  const [activeIndex, setActiveIndex] = useState(0)
  const search = (query ?? '').trim().toLowerCase()
  const options = Object.entries(airports)
    .filter(([code, name]) => `${code} ${name}`.toLowerCase().includes(search))
    .map(([code, name]) => ({ code, name }))
  if (!search) options.unshift({ code: '', name: 'All airports' })
  if (/^[a-z]{3}$/.test(search) && !airports[search.toUpperCase()]) {
    options.push({ code: search.toUpperCase(), name: 'Search this airport code' })
  }
  const active = Math.min(activeIndex, options.length - 1)
  const display = value ? `${value}${airports[value] ? ` · ${airports[value]}` : ''}` : ''

  useEffect(() => {
    function closeOutside(event) {
      if (!rootRef.current?.contains(event.target)) { setOpen(false); setQuery(null) }
    }
    document.addEventListener('pointerdown', closeOutside)
    return () => document.removeEventListener('pointerdown', closeOutside)
  }, [])

  useEffect(() => {
    if (open) listRef.current?.children[active]?.scrollIntoView({ block: 'nearest' })
  }, [open, active, search])

  function choose(option) {
    if (!option) return
    onChange(option.code)
    setOpen(false)
    setQuery(null)
  }

  function keyDown(event) {
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault()
      setOpen(true)
      setActiveIndex(!open ? 0 : Math.max(0, Math.min(options.length - 1, active + (event.key === 'ArrowDown' ? 1 : -1))))
    } else if (open && (event.key === 'Home' || event.key === 'End')) {
      event.preventDefault()
      setActiveIndex(event.key === 'Home' ? 0 : options.length - 1)
    } else if (open && event.key === 'Enter') {
      event.preventDefault()
      choose(options[active])
    } else if (event.key === 'Escape') {
      if (open) event.preventDefault()
      setOpen(false)
      setQuery(null)
    }
  }

  return <div className="airport-picker" ref={rootRef} onBlur={event => {
    if (!event.currentTarget.contains(event.relatedTarget)) { setOpen(false); setQuery(null) }
  }}>
    <label htmlFor={id}>{label}</label>
    <div className="airport-combobox">
      <input id={id} role="combobox" autoComplete="off" spellCheck={false}
        aria-autocomplete="list" aria-expanded={open} aria-controls={`${id}-options`}
        aria-activedescendant={open && active >= 0 ? `${id}-option-${active}` : undefined}
        placeholder="All airports" value={query ?? display}
        onFocus={() => { setOpen(true); setQuery(''); setActiveIndex(0) }}
        onClick={() => setOpen(true)} onKeyDown={keyDown}
        onChange={event => {
          const text = event.target.value
          setQuery(text)
          setOpen(true)
          setActiveIndex(0)
          const code = text.trim().toUpperCase()
          if (!code || airports[code]) onChange(code)
        }} />
      <svg className="airport-chevron" width="12" height="8" viewBox="0 0 12 8" aria-hidden="true"><path d="m1 1 5 5 5-5" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" /></svg>
    </div>
    {open && <div className="airport-popover">
      <div className="airport-popover-caption">Search by airport code or city</div>
      <div id={`${id}-options`} role="listbox" aria-label={`${label} options`} className="airport-options" ref={listRef}>
        {options.map((option, index) => <button type="button" role="option" tabIndex={-1}
          id={`${id}-option-${index}`} key={option.code} aria-selected={value === option.code}
          className={`airport-option ${index === active ? 'airport-option--active' : ''}`}
          onMouseDown={event => event.preventDefault()} onClick={() => choose(option)}>
          <span className="airport-option-code">{option.code || 'ALL'}</span>
          <span className="airport-option-name">{option.name}</span>
          {value === option.code && <span className="airport-option-check" aria-hidden="true">✓</span>}
        </button>)}
      </div>
      {!options.length && <p className="airport-empty" role="status">No matching airport. Try a city or a three-letter code.</p>}
    </div>}
  </div>
}
