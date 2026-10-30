<script>
  import { onMount } from 'svelte';
  import { fetchEvents } from '$lib/api.js';
  import ConfidenceBadge from '$lib/components/ConfidenceBadge.svelte';

  let events = [];
  let total = 0;
  let selectedTheme = '';
  let loading = true;

  const THEMES = [
    { value: '', label: 'Todos os temas' },
    { value: 'trabalho', label: 'Trabalho & Sindicalismo' },
    { value: 'economia', label: 'Economia & Finanças' },
    { value: 'terra_e_agronegocio', label: 'Terra & Agronegócio' },
    { value: 'politica_institucional', label: 'Política Institucional' },
    { value: 'seguranca_e_estado', label: 'Segurança & Estado' },
    { value: 'politica_externa', label: 'Política Externa & Imperialismo' },
    { value: 'meio_ambiente', label: 'Meio Ambiente' },
    { value: 'saude_educacao', label: 'Saúde & Educação' },
    { value: 'cultura', label: 'Cultura' },
    { value: 'outros', label: 'Outros' }
  ];

  async function loadEvents() {
    loading = true;
    const data = await fetchEvents({ theme: selectedTheme, limit: 20, offset: 0 });
    events = data.items || [];
    total = data.total || 0;
    loading = false;
  }

  onMount(() => {
    loadEvents();
  });
</script>

<div class="min-h-screen bg-[#0d0d0d] text-[#f4f1ea] flex flex-col">
  <!-- Faixa superior com declaração editorial obrigatória -->
  <div class="bg-[#9e1b1b] text-[#f4f1ea] px-4 py-2 text-center font-mono text-xs tracking-wide border-b border-[#e5a93c]/40">
    <strong>PREMISSA EDITORIAL:</strong> Toda notícia tem enquadramento. Análise sob ótica marxista-leninista.
  </div>

  <!-- Cabeçalho -->
  <header class="border-b border-[#2b2b2b] bg-[#121212] px-4 sm:px-8 py-8">
    <div class="max-w-6xl mx-auto flex flex-col md:flex-row md:items-end justify-between gap-6">
      <div class="space-y-2">
        <div class="inline-flex items-center gap-2 font-mono text-xs uppercase tracking-widest text-[#e5a93c]">
          <span class="w-2 h-2 bg-[#9e1b1b]"></span>
          <span>Leitura Crítica da Mídia &amp; Materialismo Histórico</span>
        </div>
        <h1 class="font-serif text-4xl sm:text-5xl font-bold tracking-tight text-[#f4f1ea]">
          CONTRAPONTO
        </h1>
        <p class="text-sm sm:text-base text-gray-300 max-w-2xl">
          Dossiês de Contradição construídos a partir do confronto entre coberturas jornalísticas, decomposição de viés e verificação programática de evidências textuais.
        </p>
      </div>

      <!-- Filtro por Tema + Modos Estúdio e Live -->
      <div class="flex flex-col sm:flex-row sm:items-end gap-3">
        <div class="flex gap-2">
          <a
            href="/studio"
            class="inline-flex items-center gap-2 px-4 py-2 rounded font-mono text-xs font-bold uppercase tracking-wider bg-[#161616] text-[#a6ff00] border border-[#a6ff00]/60 hover:bg-[#a6ff00] hover:text-black"
          >
            ✎ Modo Estúdio (Ensaios)
          </a>
          <a
            href="/live"
            class="inline-flex items-center gap-2 px-4 py-2 rounded font-mono text-xs font-bold uppercase tracking-wider bg-[#9e1b1b] text-[#f4f1ea] border border-[#e5a93c]/60 hover:bg-[#b52222]"
          >
            ● Modo Live (OBS)
          </a>
        </div>

        <div class="flex flex-col gap-1.5">
          <label for="theme-select" class="font-mono text-[11px] uppercase tracking-wider text-gray-400">
            Filtrar acontecimentos por tema
          </label>
          <select
            id="theme-select"
            bind:value={selectedTheme}
            on:change={loadEvents}
            class="bg-[#161616] border border-[#2b2b2b] rounded px-3.5 py-2 text-xs font-mono text-[#f4f1ea] focus:outline-none focus:border-[#e5a93c]"
          >
            {#each THEMES as t}
              <option value={t.value}>{t.label}</option>
            {/each}
          </select>
        </div>
      </div>
    </div>
  </header>

  <!-- Lista de Acontecimentos / Dossiês -->
  <main class="flex-1 max-w-6xl w-full mx-auto px-4 sm:px-8 py-8 space-y-6">
    <div class="flex items-center justify-between border-b border-[#2b2b2b] pb-3">
      <h2 class="font-mono text-xs uppercase tracking-widest text-[#e5a93c]">
        Dossiês de Contradição Disponíveis ({total})
      </h2>
      <span class="font-mono text-xs text-gray-400">
        Selecione um acontecimento para iniciar a apresentação em 6 cenas
      </span>
    </div>

    {#if loading}
      <div class="p-10 rounded-lg bg-[#161616] border border-[#2b2b2b] text-center font-mono text-sm text-gray-400">
        Carregando dossiês de acontecimentos...
      </div>
    {:else if events.length === 0}
      <div class="p-10 rounded-lg bg-[#161616] border border-[#2b2b2b] text-center space-y-2">
        <p class="font-serif text-xl text-[#f4f1ea]">Nenhum acontecimento encontrado para este filtro.</p>
        <p class="font-mono text-xs text-gray-400">Altere o tema selecionado acima para listar todos os eventos.</p>
      </div>
    {:else}
      <div class="space-y-5">
        {#each events as ev (ev.id)}
          <article
            class="p-6 rounded-lg bg-[#161616] border border-[#2b2b2b] hover:border-[#e5a93c]/60 scene-transition flex flex-col lg:flex-row lg:items-center justify-between gap-6"
          >
            <div class="space-y-3 max-w-3xl">
              <div class="flex flex-wrap items-center gap-2 text-xs font-mono">
                {#if ev.is_demo}
                  <span
                    class="px-2 py-0.5 rounded bg-[#e5a93c]/20 text-[#e5a93c] border border-[#e5a93c] font-bold uppercase"
                  >
                    DEMO
                  </span>
                {/if}
                <span class="px-2 py-0.5 rounded bg-[#9e1b1b]/25 text-[#f4f1ea] border border-[#9e1b1b]">
                  {ev.tema}
                </span>
                {#if ev.local}
                  <span class="text-gray-400">📍 {ev.local}</span>
                {/if}
                <span class="text-gray-400">
                  • Coesão semântica: {(Number(ev.score_coesao || 0) * 100).toFixed(0)}%
                </span>
                <span class="text-gray-400">
                  • {ev.articles_count} {ev.articles_count === 1 ? 'matéria' : 'matérias'}
                </span>
              </div>

              <h3 class="font-serif text-2xl sm:text-3xl font-bold text-[#f4f1ea] leading-snug">
                <a href={`/event/${ev.id}`} class="hover:text-[#e5a93c]">
                  {ev.titulo_provisorio}
                </a>
              </h3>

              <p class="text-sm text-gray-300 leading-relaxed">
                {ev.resumo}
              </p>

              {#if ev.confidence !== null && ev.confidence !== undefined}
                <div class="pt-1">
                  <ConfidenceBadge confidence={ev.confidence} />
                </div>
              {/if}
            </div>

            <div class="flex flex-col sm:flex-row lg:flex-col items-stretch sm:items-center lg:items-end gap-2.5 shrink-0">
              <a
                href={`/event/${ev.id}`}
                class="inline-flex items-center justify-center gap-2 px-5 py-3 rounded font-mono text-xs font-bold uppercase tracking-wider bg-[#9e1b1b] text-[#f4f1ea] border border-[#e5a93c]/50 hover:bg-[#b52222]"
              >
                <span>Abrir Dossiê de Contradição</span>
                <span aria-hidden="true">→</span>
              </a>
              <a
                href={`/studio?from_event=${encodeURIComponent(ev.id)}`}
                class="inline-flex items-center justify-center gap-2 px-4 py-2 rounded font-mono text-[11px] font-bold uppercase tracking-wider bg-[#121216] text-[#a6ff00] border border-[#a6ff00]/50 hover:bg-[#a6ff00] hover:text-black"
              >
                <span>✎ Criar Ensaio no Estúdio</span>
              </a>
            </div>
          </article>
        {/each}
      </div>
    {/if}
  </main>
</div>
