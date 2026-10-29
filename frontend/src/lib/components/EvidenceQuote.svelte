<script>
  export let quote = '';
  export let context = '';
  export let verified = false;
  export let sourceUrl = '';
  export let sourceName = '';
</script>

<blockquote
  class="p-3.5 rounded bg-[#121212] border-l-4 {verified
    ? 'border-[#e5a93c]'
    : 'border-[#9e1b1b] opacity-85'} border-t border-r border-b border-t-[#2b2b2b] border-r-[#2b2b2b] border-b-[#2b2b2b] space-y-2"
>
  <div class="flex flex-wrap items-center justify-between gap-2">
    {#if verified}
      <span
        class="inline-flex items-center gap-1.5 px-2 py-0.5 text-[11px] font-mono uppercase tracking-wider rounded bg-emerald-950/80 text-emerald-300 border border-emerald-700/70"
      >
        <span aria-hidden="true">✓</span>
        <span>verificado</span>
      </span>
    {:else}
      <span
        class="inline-flex items-center gap-1.5 px-2 py-0.5 text-[11px] font-mono uppercase tracking-wider rounded bg-[#9e1b1b]/30 text-red-200 border border-[#9e1b1b]"
      >
        <span aria-hidden="true">⚠</span>
        <span>não verificado</span>
      </span>
    {/if}

    {#if sourceUrl}
      <a
        href={sourceUrl}
        target="_blank"
        rel="noopener noreferrer"
        class="text-[11px] font-mono text-[#e5a93c] hover:underline"
      >
        {sourceName ? `Fonte: ${sourceName} ↗` : 'Ver matéria original ↗'}
      </a>
    {/if}
  </div>

  <p class="font-serif italic text-sm md:text-base text-[#f4f1ea] leading-relaxed">
    “{quote}”
  </p>

  {#if context && context !== 'sem_evidencia_suficiente'}
    <footer class="text-xs text-gray-400 leading-snug">
      <span class="font-mono uppercase text-[10px] text-gray-500 mr-1">Contexto:</span>
      {context}
    </footer>
  {/if}
</blockquote>
