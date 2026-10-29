<script>
  import { createEventDispatcher, onMount } from 'svelte';

  export let currentScene = 0;
  export let totalScenes = 6;

  const dispatch = createEventDispatcher();
  let viewportEl;
  let wheelCooldown = false;

  const SCENE_NAMES = [
    '01 FATO',
    '02 DISPUTA',
    '03 MAPA DE PODER',
    '04 DADOS',
    '05 ANÁLISE ML',
    '06 FONTES'
  ];

  export function goToScene(index) {
    const clamped = Math.max(0, Math.min(totalScenes - 1, index));
    if (clamped !== currentScene) {
      currentScene = clamped;
      dispatch('change', currentScene);
      if (viewportEl && typeof viewportEl.scrollTo === 'function') {
        viewportEl.scrollTo({ top: 0 });
      }
    }
  }

  export function nextScene() {
    if (currentScene < totalScenes - 1) {
      goToScene(currentScene + 1);
    }
  }

  export function prevScene() {
    if (currentScene > 0) {
      goToScene(currentScene - 1);
    }
  }

  function handleKeydown(event) {
    const tag = event.target?.tagName?.toLowerCase();
    if (tag === 'input' || tag === 'textarea' || tag === 'select') return;

    if (event.key === 'ArrowRight') {
      event.preventDefault();
      nextScene();
    } else if (event.key === 'ArrowLeft') {
      event.preventDefault();
      prevScene();
    }
  }

  function handleWheel(event) {
    // Suporte a navegação por scroll horizontal (trackpad deltaX ou Shift+Scroll)
    if (Math.abs(event.deltaX) > 45 && Math.abs(event.deltaX) > Math.abs(event.deltaY)) {
      if (wheelCooldown) return;
      wheelCooldown = true;
      if (event.deltaX > 0) {
        nextScene();
      } else {
        prevScene();
      }
      setTimeout(() => {
        wheelCooldown = false;
      }, 420);
    }
  }

  onMount(() => {
    window.addEventListener('keydown', handleKeydown);
    return () => {
      window.removeEventListener('keydown', handleKeydown);
    };
  });
</script>

<div
  bind:this={viewportEl}
  on:wheel={handleWheel}
  class="relative min-h-[calc(100vh-56px)] flex flex-col justify-between bg-[#0d0d0d] text-[#f4f1ea]"
>
  <main class="flex-1 w-full max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 md:py-10 scene-transition">
    <slot />
  </main>

  <footer
    class="no-print sticky bottom-0 z-30 bg-[#0d0d0d]/95 backdrop-blur border-t border-[#2b2b2b] px-4 sm:px-8 py-3"
  >
    <div class="max-w-7xl mx-auto flex items-center justify-between gap-4">
      <button
        type="button"
        on:click={prevScene}
        disabled={currentScene === 0}
        class="inline-flex items-center gap-2 px-4 py-2 rounded font-mono text-xs uppercase tracking-wider border border-[#2b2b2b] bg-[#161616] text-[#f4f1ea] hover:border-[#e5a93c] disabled:opacity-35 disabled:pointer-events-none"
      >
        <span>← Anterior</span>
        {#if currentScene > 0}
          <span class="hidden sm:inline text-gray-400">({SCENE_NAMES[currentScene - 1]})</span>
        {/if}
      </button>

      <div class="text-center font-mono text-xs text-gray-400">
        Cena <strong class="text-[#e5a93c]">{currentScene + 1}</strong> de {totalScenes}
        <span class="hidden md:inline ml-2 text-gray-500">• Navegue com ← → ou botões</span>
      </div>

      <button
        type="button"
        on:click={nextScene}
        disabled={currentScene >= totalScenes - 1}
        class="inline-flex items-center gap-2 px-4 py-2 rounded font-mono text-xs uppercase tracking-wider border border-[#9e1b1b] bg-[#9e1b1b] text-[#f4f1ea] hover:bg-[#b52222] disabled:opacity-35 disabled:pointer-events-none"
      >
        <span>Próxima →</span>
        {#if currentScene < totalScenes - 1}
          <span class="hidden sm:inline text-[#f4f1ea]/80">({SCENE_NAMES[currentScene + 1]})</span>
        {/if}
      </button>
    </div>
  </footer>
</div>
