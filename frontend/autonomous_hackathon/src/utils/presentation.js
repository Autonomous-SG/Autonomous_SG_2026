export const humanize = value => String(value ?? 'Unknown').replaceAll('_', ' ').toLowerCase()
export const minutes = value => value == null ? '—' : `${value > 0 ? '+' : ''}${value} min`

export function isSynthetic(world, path) {
  return (world.public.synthetic_fields ?? []).some(field => {
    const normalized = field.startsWith('public.') ? field.slice(7) : field
    const target = path.startsWith('public.') ? path.slice(7) : path
    return field === 'public' || target === normalized || target.startsWith(`${normalized}.`)
  })
}

export function vetoState(round, optionId, assessment) {
  if (assessment.verdict !== 'VETO') return null
  // RuleCheck has no option_id. Do not infer a per-option confirmation from
  // another option's check; eliminated is the authoritative option-level result.
  return round.eliminated.includes(optionId) ? 'Option eliminated' : 'Veto did not eliminate option'
}
