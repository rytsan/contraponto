<script>
  export let confidence = 0.0;
  export let label = 'Confiança Verificada (Etapa 3.3)';

  $: pct = Math.round((Number(confidence) || 0) * 100);
  $: badgeColorClass =
    pct >= 80
      ? 'border-emerald-700/80 bg-emerald-950/60 text-emerald-300'
      : pct >= 50
        ? 'border-[#e5a93c]/80 bg-[#e5a93c]/15 text-[#e5a93c]'
        : 'border-[#9e1b1b] bg-[#9e1b1b]/20 text-red-300';
</script>

<div
  class="inline-flex items-center gap-2 px-3 py-1 rounded border text-xs font-mono {badgeColorClass}"
  title="Calculado programaticamente pelo sistema (citações verificadas ÷ total de citações)"
>
  <span class="uppercase tracking-wider opacity-85">{label}:</span>
  <strong class="text-sm">{pct}%</strong>
  <span class="opacity-70">({Number(confidence || 0).toFixed(2)})</span>
</div>
