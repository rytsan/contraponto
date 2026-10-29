<script>
  import { createEventDispatcher } from 'svelte';

  export let currentScene = 0;
  export let isDemo = false;

  const dispatch = createEventDispatcher();

  export const SCENES = [
    { index: 0, code: '01', label: 'FATO' },
    { index: 1, code: '02', label: 'DISPUTA' },
    { index: 2, code: '03', label: 'MAPA DE PODER' },
    { index: 3, code: '04', label: 'DADOS' },
    { index: 4, code: '05', label: 'ANÁLISE ML' },
    { index: 5, code: '06', label: 'FONTES' }
  ];

  function selectScene(index) {
    dispatch('select', index);
  }
</script>

<header
  class="no-print sticky top-0 z-40 w-full bg-[#0d0d0d]/95 backdrop-blur border-b border-[#2b2b2b] px-3 md:px-6 py-2.5"
>
  <div class="max-w-7xl mx-auto flex flex-col lg:flex-row lg:items-center lg:justify-between gap-2">
    <div class="flex items-center justify-between gap-3">
      <div class="flex items-center gap-2.5">
        <a
          href="/"
          class="font-serif font-bold tracking-tight text-lg text-[#f4f1ea] hover:text-[#e5a93c] flex items-center gap-2"
        >
          <span class="inline-block w-2.5 h-2.5 bg-[#9e1b1b]"></span>
          <span>CONTRAPONTO</span>
        </a>
        {#if isDemo}
          <span
            class="px-2 py-0.5 text-[10px] font-mono uppercase tracking-widest bg-[#e5a93c]/20 text-[#e5a93c] border border-[#e5a93c] rounded"
          >
            DEMO SINTÉTICO
          </span>
        {/if}
      </div>
      <span class="text-[11px] font-mono text-gray-400 hidden sm:inline lg:hidden">
        Use ← → ou clique nas cenas
      </span>
    </div>

    <nav aria-label="Progresso do Dossiê de Contradição" class="overflow-x-auto py-1">
      <ol class="flex items-center gap-1 md:gap-1.5 min-w-max font-mono text-xs">
        {#each SCENES as scene, idx}
          <li class="flex items-center">
            <button
              type="button"
              on:click={() => selectScene(scene.index)}
              aria-current={currentScene === scene.index ? 'step' : undefined}
              class="px-2.5 py-1 rounded border scene-transition {currentScene === scene.index
                ? 'bg-[#9e1b1b] text-[#f4f1ea] border-[#e5a93c] font-bold shadow-sm'
                : currentScene > scene.index
                  ? 'bg-[#161616] text-[#e5a93c] border-[#2b2b2b] hover:border-[#e5a93c]/60'
                  : 'bg-[#121212] text-gray-400 border-[#2b2b2b] hover:text-[#f4f1ea]'}"
            >
              [ {scene.code} {scene.label} ]
            </button>
            {#if idx < SCENES.length - 1}
              <span class="mx-1 text-gray-600 select-none" aria-hidden="true">-&gt;</span>
            {/if}
          </li>
        {/each}
      </ol>
    </nav>
  </div>
</header>
