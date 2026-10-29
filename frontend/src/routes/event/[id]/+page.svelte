<script>
  import { onDestroy, onMount } from 'svelte';
  import { page } from '$app/stores';
  import {
    DEMO_FALLBACK_DOSSIER,
    fetchAnalysisStatus,
    fetchEventDetail,
    fetchEventDossier,
    triggerEventAnalysis
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
  let dossier = null;
  let eventSummary = null;
  let loading = true;
  let analysisJob = null;
  let pollTimer = null;

  $: eventId = $page.params.id || 'demo-event-transporte-sp-2026';

  function stopPolling() {
    if (pollTimer) {
      clearInterval(pollTimer);
      pollTimer = null;
    }
  }

  async function pollAnalysisProgress(id) {
    stopPolling();
    pollTimer = setInterval(async () => {
      try {
        const st = await fetchAnalysisStatus(id);
        analysisJob = st;
        if (st.status === 'completed') {
          stopPolling();
          await loadEventAndDossier(id);
        } else if (st.status === 'failed') {
          stopPolling();
        }
      } catch {
        stopPolling();
      }
    }, 1500);
  }

  async function handleStartAnalysis() {
    try {
      analysisJob = {
        status: 'queued',
        stage: 'enfileirando',
        articles_done: 0,
        articles_total: eventSummary?.articles_count || 2,
        error: null
      };
      await triggerEventAnalysis(eventId);
      const st = await fetchAnalysisStatus(eventId);
      analysisJob = st;
      if (st.status === 'completed') {
        await loadEventAndDossier(eventId);
      } else {
        await pollAnalysisProgress(eventId);
      }
    } catch (err) {
      analysisJob = {
        status: 'failed',
        stage: 'erro',
        articles_done: 0,
        articles_total: 0,
        error: err.message
      };
    }
  }

  async function loadEventAndDossier(id) {
    loading = true;
    try {
      const detail = await fetchEventDetail(id);
      eventSummary = detail;
      if (detail?.dossier) {
        dossier = detail.dossier;
      } else if (detail?.has_dossier) {
        dossier = await fetchEventDossier(id);
      } else if (id === 'demo-event-transporte-sp-2026') {
        dossier = DEMO_FALLBACK_DOSSIER;
      } else {
        dossier = null;
        try {
          const st = await fetchAnalysisStatus(id);
          analysisJob = st;
          if (st.status === 'running') {
            pollAnalysisProgress(id);
          }
        } catch {
          analysisJob = null;
        }
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

  onDestroy(() => {
    stopPolling();
  });
</script>

<svelte:head>
  <title>{dossier?.title || eventSummary?.titulo_provisorio || 'Dossiê de Contradição'} — Contraponto</title>
</svelte:head>

<div class="min-h-screen bg-[#0d0d0d] text-[#f4f1ea] flex flex-col">
  <DossierProgress
    {currentScene}
    isDemo={Boolean(dossier?.is_demo ?? eventSummary?.is_demo)}
    on:select={(e) => (currentScene = e.detail)}
  />

  {#if analysisJob && (analysisJob.status === 'queued' || analysisJob.status === 'running')}
    <div class="no-print bg-[#161616] border-b border-[#e5a93c]/50 px-4 py-2.5 text-xs font-mono flex items-center justify-between max-w-7xl w-full mx-auto">
      <span class="text-[#e5a93c]">
        ⟳ Análise assíncrona em andamento ({analysisJob.stage}): {analysisJob.articles_done}/{analysisJob.articles_total} matérias processadas...
      </span>
      <span class="text-gray-400 uppercase">{analysisJob.status}</span>
    </div>
  {:else if analysisJob && analysisJob.status === 'failed' && analysisJob.error}
    <div class="no-print bg-[#9e1b1b]/25 border-b border-[#9e1b1b] px-4 py-2.5 text-xs font-mono flex items-center justify-between max-w-7xl w-full mx-auto">
      <span class="text-red-200">Falha no job de análise: {analysisJob.error}</span>
      <button
        type="button"
        on:click={handleStartAnalysis}
        class="px-3 py-1 rounded bg-[#9e1b1b] text-[#f4f1ea]"
      >
        Retomar análise
      </button>
    </div>
  {/if}

  {#if loading}
    <div class="flex-1 flex items-center justify-center p-12 font-mono text-sm text-gray-400">
      Carregando Dossiê de Contradição...
    </div>
  {:else if !dossier}
    <div class="flex-1 flex items-center justify-center p-8">
      <div class="max-w-xl w-full p-8 rounded-lg bg-[#161616] border border-[#2b2b2b] space-y-5 text-center">
        <span class="px-2.5 py-1 rounded font-mono text-xs bg-[#9e1b1b]/25 text-[#e5a93c] border border-[#9e1b1b]">
          DOSSIÊ PENDENTE DE ANÁLISE
        </span>
        <h1 class="font-serif text-2xl sm:text-3xl font-bold text-[#f4f1ea]">
          {eventSummary?.titulo_provisorio || `Evento #${eventId}`}
        </h1>
        <p class="text-sm text-gray-300 leading-relaxed">
          Este agrupamento possui {eventSummary?.articles_count || 0} matérias coletadas e aguarda execução do pipeline local (llama-server + verificador fuzzy de citações).
        </p>
        <button
          type="button"
          on:click={handleStartAnalysis}
          class="px-6 py-3 rounded font-mono text-xs font-bold uppercase tracking-wider bg-[#9e1b1b] text-[#f4f1ea] border border-[#e5a93c]/60 hover:bg-[#b52222]"
        >
          Iniciar Análise Assíncrona (Etapas 3.1 → 3.3)
        </button>
      </div>
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
