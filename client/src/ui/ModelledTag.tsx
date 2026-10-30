export function ModelledTag({ note }: { note?: string }) {
  const tip = note ?? 'Modelled, not measured. Estimated from state-level VAHAN counts and district indicators. See Method.';
  return <span className="tag-modelled" title={tip} aria-label={`Modelled. ${tip}`}>Modelled</span>;
}
