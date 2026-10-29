<script>
  import { createEventDispatcher } from 'svelte';
  import ConfidenceBadge from './ConfidenceBadge.svelte';

  export let dossier;
  export let eventDate = '';

  const dispatch = createEventDispatcher();

  const THEME_LABELS = {
    economia: 'Economia & Finanças',
    trabalho: 'Trabalho & Sindicalismo',
    terra_e_agronegocio: 'Terra & Agronegócio',
    politica_institucional: 'Política Institucional',
    seguranca_e_estado: 'Segurança & Estado',
    politica_externa: 'Política Externa & Imperialismo',
    meio_ambiente: 'Meio Ambiente & Território',
    cultura: 'Cultura & Ideologia',
    saude_educacao: 'Saúde & Educação Pública',
    outros: 'Outros Temas'
  };

  $: sourcesCount = dossier?.coverage_pairs?.length || 0;
  $: formattedDate = eventDate
    ? new Date(eventDate).toLocaleDateString('pt-BR', {
        day: '2-digit',
        month: 'long',
        year: 'numeric'
      })
    : dossier?.audit_metadata?.analyzed_at
      ? new Date(dossier.audit_metadata.analyzed_at).toLocaleDateString('pt-BR', {
          day: '2-digit',
          month: 'long',
          year: 'numeric'
        })
      : 'Data registrada no evento';
</script>

<section aria-labelledby="scene-1-heading" class="space-y-8 py-4 md:py-8 max-w-5xl mx-auto">
  <!-- Declaração explícita de linha editorial obrigatória no topo -->
  <div
    class="border-l-4 border-[#9e1b1b] bg-[#161616] px-4 py-3 rounded-r flex flex-wrap items-center justify-between gap-3"
  >
    <p class="font-mono text-xs sm:text-sm tracking-wide text-[#f4f1ea]">
      <strong class="text-[#e5a93c] uppercase mr-2">Linha Editorial:</strong>
      Toda notícia tem enquadramento. Análise sob ótica marxista-leninista.
    </p>
    <ConfidenceBadge confidence={dossier?.confidence ?? 0} />
  </div>

  <!-- Cabeçalho e metadados do acontecimento -->
  <div class="space-y-4">
    <div class="flex flex-wrap items-center gap-2 text-xs font-mono text-gray-400">
      <span class="px-2.5 py-1 rounded bg-[#9e1b1b]/25 text-[#f4f1ea] border border-[#9e1b1b]">
        CENA 01 // FATO
      </span>
      {#if dossier?.is_demo}
        <span
          class="px-2.5 py-1 rounded bg-[#e5a93c]/20 text-[#e5a93c] border border-[#e5a93c] font-bold"
        >
          DEMO — DADOS 100% SINTÉTICOS
        </span>
      {/if}
      <span class="px-2.5 py-1 rounded bg-[#161616] border border-[#2b2b2b] text-[#e5a93c]">
        Tema: {THEME_LABELS[dossier?.theme] || dossier?.theme || 'Geral'}
      </span>
      <span class="px-2.5 py-1 rounded bg-[#161616] border border-[#2b2b2b]">
        📅 {formattedDate}
      </span>
      <span class="px-2.5 py-1 rounded bg-[#161616] border border-[#2b2b2b]">
        📍 {dossier?.location || 'Local não especificado'}
      </span>
      <span class="px-2.5 py-1 rounded bg-[#161616] border border-[#2b2b2b]">
        📰 {sourcesCount} {sourcesCount === 1 ? 'fonte analisada' : 'fontes em disputa'}
      </span>
    </div>

    <h1
      id="scene-1-heading"
      class="font-serif text-3xl sm:text-4xl lg:text-5xl font-bold text-[#f4f1ea] leading-tight tracking-tight"
    >
      {dossier?.title || `Dossiê de Contradição #${dossier?.event_id}`}
    </h1>
  </div>

  <!-- Bloco central da Âncora Factual Mínima -->
  <div class="bg-[#161616] border border-[#2b2b2b] rounded-lg p-6 sm:p-8 space-y-5 shadow-lg">
    <div class="flex items-center justify-between border-b border-[#2b2b2b] pb-3">
      <h2 class="font-mono text-xs uppercase tracking-widest text-[#e5a93c]">
        Âncora Factual Mínima
      </h2>
      <span class="font-mono text-[11px] text-gray-400">Núcleo verificável comum</span>
    </div>

    <p class="font-serif text-lg sm:text-xl md:text-2xl text-[#f4f1ea] leading-relaxed">
      {dossier?.factual_anchor || 'sem_evidencia_suficiente'}
    </p>

    <div
      class="p-4 rounded bg-[#0d0d0d] border border-[#e5a93c]/40 flex items-start gap-3 text-xs sm:text-sm text-gray-300"
    >
      <span class="text-[#e5a93c] font-bold text-base leading-none mt-0.5" aria-hidden="true">!</span>
      <p>
        <strong class="text-[#f4f1ea]">Aviso metodológico:</strong>
        Âncora factual mínima não é neutralidade. É apenas o núcleo verificável comum entre as fontes.
      </p>
    </div>
  </div>

  <!-- Ação principal para avançar à Cena 2 -->
  <div class="pt-2 flex flex-wrap items-center justify-between gap-4">
    <p class="text-xs font-mono text-gray-400">
      A partir deste fato comum, cada veículo constrói um enquadramento de classe distinto.
    </p>
    <button
      type="button"
      on:click={() => dispatch('next')}
      class="inline-flex items-center gap-3 px-6 py-3.5 rounded font-mono text-sm font-bold uppercase tracking-wider bg-[#9e1b1b] text-[#f4f1ea] border border-[#e5a93c]/60 hover:bg-[#b52222] shadow-md scene-transition"
    >
      <span>Ver a disputa</span>
      <span aria-hidden="true">→</span>
    </button>
  </div>
</section>
