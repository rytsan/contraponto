<script>
  import { getExportUrl } from '$lib/api.js';
  import EvidenceQuote from './EvidenceQuote.svelte';
  import PoliticalPositionBadge from './PoliticalPositionBadge.svelte';

  export let dossier;

  $: eventId = dossier?.event_id || 'demo-event-transporte-sp-2026';
  $: auditMeta = dossier?.audit_metadata || null;
  $: registry = auditMeta?.articles_registry || [];
  $: coveragePairs = dossier?.coverage_pairs || [];

  function findQuotesForArticle(articleId) {
    const pair = coveragePairs.find((p) => p.article_id === articleId);
    return pair?.evidence_quotes || [];
  }

  function formatDateTime(isoStr) {
    if (!isoStr) return 'N/D';
    try {
      return new Date(isoStr).toLocaleString('pt-BR', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      });
    } catch {
      return String(isoStr);
    }
  }

  function handlePrintPdf() {
    if (typeof window !== 'undefined' && typeof window.print === 'function') {
      window.print();
    }
  }
</script>

<section aria-labelledby="scene-6-heading" class="space-y-8 py-2">
  <!-- Cabeçalho e Botões de Exportação -->
  <div class="flex flex-col lg:flex-row lg:items-center justify-between gap-4 border-b border-[#2b2b2b] pb-4">
    <div class="space-y-1">
      <span class="px-2.5 py-1 rounded font-mono text-xs bg-[#9e1b1b]/25 text-[#f4f1ea] border border-[#9e1b1b]">
        CENA 06 // REGISTRO DE FONTES E AUDITORIA
      </span>
      <h2 id="scene-6-heading" class="font-serif text-2xl sm:text-3xl font-bold text-[#f4f1ea] pt-1">
        Rastreabilidade Completa, Metadados e Exportação
      </h2>
    </div>

    <div class="no-print flex flex-wrap items-center gap-2.5">
      <a
        href={getExportUrl(eventId, 'markdown')}
        target="_blank"
        rel="noopener noreferrer"
        class="inline-flex items-center gap-2 px-4 py-2.5 rounded font-mono text-xs font-bold uppercase tracking-wider bg-[#161616] text-[#e5a93c] border border-[#e5a93c]/60 hover:bg-[#1d1d1d]"
      >
        <span>⬇ Exportar Markdown (.md)</span>
      </a>
      <a
        href={getExportUrl(eventId, 'json')}
        target="_blank"
        rel="noopener noreferrer"
        class="inline-flex items-center gap-2 px-4 py-2.5 rounded font-mono text-xs font-bold uppercase tracking-wider bg-[#161616] text-[#f4f1ea] border border-[#2b2b2b] hover:border-[#e5a93c]"
      >
        <span>⬇ Exportar JSON (.json)</span>
      </a>
      <button
        type="button"
        on:click={handlePrintPdf}
        class="inline-flex items-center gap-2 px-4 py-2.5 rounded font-mono text-xs font-bold uppercase tracking-wider bg-[#9e1b1b] text-[#f4f1ea] border border-[#e5a93c]/60 hover:bg-[#b52222]"
      >
        <span>🖨️ Imprimir / Exportar PDF</span>
      </button>
    </div>
  </div>

  <!-- Aviso Obrigatório de Limite Interpretativo -->
  <div class="p-4 rounded-lg bg-[#161616] border-l-4 border-[#e5a93c] border-t border-r border-b border-t-[#2b2b2b] border-r-[#2b2b2b] border-b-[#2b2b2b] flex items-center gap-3">
    <span class="text-[#e5a93c] font-bold text-lg" aria-hidden="true">⚠</span>
    <p class="font-serif text-sm sm:text-base text-[#f4f1ea] font-semibold">
      A análise é interpretativa e não substitui a leitura das fontes originais.
    </p>
  </div>

  <!-- Metadados Técnicos do Motor de Análise Local -->
  <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
    <div class="p-4 rounded bg-[#161616] border border-[#2b2b2b]">
      <span class="block font-mono text-[10px] uppercase text-gray-400">Modelo LLM Local (llama.cpp)</span>
      <strong class="font-mono text-xs text-[#e5a93c] break-all">
        {auditMeta?.llm_model || 'Meta-Llama-3.1-8B-Instruct-Q4_K_M'}
      </strong>
    </div>
    <div class="p-4 rounded bg-[#161616] border border-[#2b2b2b]">
      <span class="block font-mono text-[10px] uppercase text-gray-400">Janela de Contexto (-c)</span>
      <strong class="font-mono text-sm text-[#f4f1ea]">
        {auditMeta?.num_ctx || 8192} tokens
      </strong>
    </div>
    <div class="p-4 rounded bg-[#161616] border border-[#2b2b2b]">
      <span class="block font-mono text-[10px] uppercase text-gray-400">Data da Análise</span>
      <strong class="font-mono text-xs text-[#f4f1ea]">
        {formatDateTime(auditMeta?.analyzed_at)}
      </strong>
    </div>
    <div class="p-4 rounded bg-[#161616] border border-[#2b2b2b]">
      <span class="block font-mono text-[10px] uppercase text-gray-400">Confiança Recalculada (Etapa 3.3)</span>
      <strong class="font-mono text-sm text-emerald-400">
        {Math.round((Number(dossier?.confidence) || 0) * 100)}% ({Number(dossier?.confidence || 0).toFixed(2)})
      </strong>
    </div>
  </div>

  <!-- Lista Completa de Matérias Utilizadas e Trechos Citados -->
  <div class="space-y-4">
    <h3 class="font-mono text-xs uppercase tracking-widest text-[#e5a93c]">
      Matérias Fontes Auditadas ({registry.length > 0 ? registry.length : coveragePairs.length})
    </h3>

    {#if registry.length > 0}
      <div class="space-y-5">
        {#each registry as item (item.id)}
          {@const itemQuotes = findQuotesForArticle(item.id)}
          <article class="p-5 rounded-lg bg-[#161616] border border-[#2b2b2b] space-y-4">
            <div class="flex flex-col md:flex-row md:items-start justify-between gap-3 border-b border-[#2b2b2b] pb-3">
              <div class="space-y-1.5">
                <div class="flex flex-wrap items-center gap-2 font-mono text-xs">
                  <span class="text-[#e5a93c] font-bold">{item.veiculo}</span>
                  <span class="px-2 py-0.5 rounded bg-[#121212] border border-[#2b2b2b] text-gray-300">
                    Método: {item.metodo_coleta}
                  </span>
                  <span class="text-gray-400">ID: {item.id}</span>
                </div>
                <h4 class="font-serif text-xl font-bold text-[#f4f1ea]">{item.titulo}</h4>
                <PoliticalPositionBadge
                  position={item.posicao_editorial_declarada}
                  isDemo={Boolean(item.is_demo || dossier?.is_demo)}
                />
              </div>

              <a
                href={item.url_canonica}
                target="_blank"
                rel="noopener noreferrer"
                class="px-3.5 py-2 rounded font-mono text-xs bg-[#1d1d1d] border border-[#e5a93c]/50 text-[#e5a93c] hover:bg-[#9e1b1b] hover:text-[#f4f1ea] shrink-0 self-start"
              >
                Ler fonte original ↗
              </a>
            </div>

            <div class="grid grid-cols-1 sm:grid-cols-3 gap-3 font-mono text-xs text-gray-300">
              <div>
                <span class="text-gray-500 block text-[10px] uppercase">Autor</span>
                {item.autor || 'Redação / Não informado'}
              </div>
              <div>
                <span class="text-gray-500 block text-[10px] uppercase">Data de Publicação</span>
                {formatDateTime(item.data_publicacao)}
              </div>
              <div>
                <span class="text-gray-500 block text-[10px] uppercase">Data de Coleta</span>
                {formatDateTime(item.data_coleta)}
              </div>
            </div>

            {#if itemQuotes.length > 0}
              <div class="space-y-2 pt-2 border-t border-[#2b2b2b]">
                <span class="block font-mono text-[11px] uppercase tracking-wider text-gray-400">
                  Trechos Citados desta Matéria ({itemQuotes.length}):
                </span>
                <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {#each itemQuotes as q}
                    <EvidenceQuote
                      quote={q.quote}
                      context={q.context}
                      verified={q.verified}
                      sourceUrl={item.url_canonica}
                      sourceName={item.veiculo}
                    />
                  {/each}
                </div>
              </div>
            {/if}
          </article>
        {/each}
      </div>
    {:else}
      <!-- Fallback usando coveragePairs caso audit_metadata não tenha sido populado -->
      <div class="space-y-5">
        {#each coveragePairs as pair (pair.article_id)}
          <article class="p-5 rounded-lg bg-[#161616] border border-[#2b2b2b] space-y-4">
            <div class="flex flex-col md:flex-row md:items-start justify-between gap-3 border-b border-[#2b2b2b] pb-3">
              <div class="space-y-1.5">
                <span class="font-mono text-xs text-[#e5a93c] font-bold">{pair.source}</span>
                <h4 class="font-serif text-xl font-bold text-[#f4f1ea]">{pair.headline}</h4>
                <PoliticalPositionBadge
                  position={pair.source_position}
                  isDemo={Boolean(dossier?.is_demo)}
                />
              </div>
              <a
                href={pair.url}
                target="_blank"
                rel="noopener noreferrer"
                class="px-3.5 py-2 rounded font-mono text-xs bg-[#1d1d1d] border border-[#e5a93c]/50 text-[#e5a93c]"
              >
                Ler fonte original ↗
              </a>
            </div>
          </article>
        {/each}
      </div>
    {/if}
  </div>
</section>
