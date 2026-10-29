<script>
  export let position = 'Posição editorial não declarada';
  export let isDemo = false;
</script>

<div class="inline-flex flex-wrap items-center gap-2">
  {#if isDemo}
    <span
      class="inline-flex items-center px-2 py-0.5 text-[11px] font-mono uppercase tracking-wider bg-[#e5a93c]/20 text-[#e5a93c] border border-[#e5a93c]/60 rounded"
      title="Dados 100% sintéticos de demonstração"
    >
      DEMO
    </span>
  {/if}
  <span
    class="inline-flex items-center px-2.5 py-1 text-xs font-mono tracking-wide bg-[#1d1d1d] text-[#f4f1ea]/90 border border-[#2b2b2b] rounded"
  >
    <span class="w-1.5 h-1.5 rounded-full bg-[#9e1b1b] mr-2 shrink-0"></span>
    <span>Posição editorial: {position}</span>
  </span>
</div>
