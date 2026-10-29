<script>
  import { onMount } from 'svelte';
  import { page } from '$app/stores';
  import {
    DEMO_FALLBACK_DOSSIER,
    fetchEventDetail,
    fetchEventDossier
  } from '$lib/api.js';
  import CoverageComparison from '$lib/components/CoverageComparison.svelte';
  import DataPanel from '$lib/components/DataPanel.svelte';
  import DossierProgress from '$lib/components/DossierProgress.svelte';
  import FactualAnchor from '$lib/components/FactualAnchor.svelte';
  import MarxistAnalysis from '$lib/components/MarxistAnalysis.svelte';
  import PowerMap from '$lib/components/PowerMap.svelte';
  import SceneContainer from '$lib/components/SceneContainer.svelte';
  import SourceRegistry from '$lib/components/SourceRegistry.svelte';

  let currentScene = 0;
  let dossier = DEMO_FALLBACK_DOSSIER;
  let eventSummary = null;
  let loading = true;

  $: eventId = $page.params.id || 'demo-event-transporte-sp-2026';

  async function loadEventAndDossier(id) {
    loading = true;
    try {
      const detail = await fetchEventDetail(id);
      eventSummary = detail;
      if (detail?.dossier) {
        dossier = detail.dossier;
      } else {
        dossier = await fetchEventDossier(id);
      }
    } catch {
      dossier = { ...DEMO_FALLBACK_DOSSIER, event_id: id };
    } finally {
      loading = false;
    }
  }

  onMount(() => {
    loadEventAndDossier(eventId);
  });
</script>

<svelte:head>
  <title>{dossier?.title || 'Dossiê de Contradição'} — Contraponto</title>
</svelte:head>

<div class="min-h-screen bg-[#0d0d0d] text-[#f4f1ea] flex flex-col">
  <DossierProgress
    {currentScene}
    isDemo={Boolean(dossier?.is_demo)}
    on:select={(e) => (currentScene = e.detail)}
  />

  {#if loading}
    <div class="flex-1 flex items-center justify-center p-12 font-mono text-sm text-gray-400">
      Carregando Dossiê de Contradição...
    </div>
  {:else}
    <!-- Apresentação Interativa em 6 Cenas (Tela) -->
    <div class="no-print">
      <SceneContainer
        bind:currentScene
        totalScenes={6}
        on:change={(e) => (currentScene = e.detail)}
      >
        {#if currentScene === 0}
          <FactualAnchor
            {dossier}
            eventDate={eventSummary?.periodo_fim || ''}
            on:next={() => (currentScene = 1)}
          />
        {:else if currentScene === 1}
          <CoverageComparison
            coveragePairs={dossier?.coverage_pairs || []}
            isDemo={Boolean(dossier?.is_demo)}
          />
        {:else if currentScene === 2}
          <PowerMap {dossier} />
        {:else if currentScene === 3}
          <DataPanel
            dataVisualizations={dossier?.data_visualizations || []}
            coveragePairs={dossier?.coverage_pairs || []}
            articlesRegistry={dossier?.audit_metadata?.articles_registry || []}
          />
        {:else if currentScene === 4}
          <MarxistAnalysis
            analysis={dossier?.marxist_leninist_analysis || {}}
            readerQuestions={dossier?.reader_questions || []}
            coveragePairs={dossier?.coverage_pairs || []}
            confidence={dossier?.confidence ?? 0}
          />
        {:else if currentScene === 5}
          <SourceRegistry {dossier} />
        {/if}
      </SceneContainer>
    </div>

    <!-- Versão Linear Completa exclusiva para Impressão / Exportação PDF (@media print) -->
    <div class="hidden print-all-scenes px-8 py-6">
      <div class="print-scene-section">
        <FactualAnchor {dossier} eventDate={eventSummary?.periodo_fim || ''} />
      </div>
      <div class="print-scene-section">
        <CoverageComparison
          coveragePairs={dossier?.coverage_pairs || []}
          isDemo={Boolean(dossier?.is_demo)}
        />
      </div>
      <div class="print-scene-section">
        <MarxistAnalysis
          analysis={dossier?.marxist_leninist_analysis || {}}
          readerQuestions={dossier?.reader_questions || []}
          coveragePairs={dossier?.coverage_pairs || []}
          confidence={dossier?.confidence ?? 0}
        />
      </div>
      <div class="print-scene-section">
        <SourceRegistry {dossier} />
      </div>
    </div>
  {/if}
</div>
