/* Sağlayıcı: Ollama (bilgisayarda ya da fakülte sunucusunda çalışan açık model). Ücretsizdir;
 * soru cihazdan/fakülteden çıkmaz. Tarayıcıdan erişim için Ollama'nın OLLAMA_ORIGINS ayarı
 * bu sayfanın adresine izin vermelidir (README'ye bakın). */
(function (AT) {
  'use strict';

  function toolCalls(msg) {
    for (const c of (msg && msg.tool_calls) || []) {
      const f = c.function || {};
      if (f.name !== 'tahtaya_yaz') continue;
      let a = f.arguments;
      if (typeof a === 'string') { try { a = JSON.parse(a); } catch (e) { a = null; } }
      if (a && Array.isArray(a.komutlar)) return a;
    }
    return null;
  }

  AT.qa.registerProvider('ollama', {
    label: 'Ollama (yerel model)',
    kind: 'local',
    needsKey: false,
    defaultModel: 'qwen2.5:3b',
    defaultBaseURL: 'http://localhost:11434',
    tools: true,

    async chat({ system, messages, tools, signal, model, baseURL }) {
      const body = {
        model, stream: false,
        messages: [{ role: 'system', content: system }, ...messages],
        options: { temperature: 0.2 }
      };
      if (tools.length) body.tools = tools.map((t) => ({ type: 'function', function: { name: t.name, description: t.description, parameters: t.parameters } }));
      let r;
      try {
        r = await fetch(baseURL.replace(/\/+$/, '') + '/api/chat', {
          method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body), signal
        });
      } catch (e) {
        if (e.name === 'AbortError') throw e;
        throw new Error('Ollama\'ya ulaşılamadı (' + baseURL + '). Ollama açık mı, OLLAMA_ORIGINS ayarlı mı?');
      }
      if (!r.ok) {
        const t = await r.text().catch(() => '');
        if (tools.length && /does not support tools/i.test(t)) throw new Error('Bu model araç çağrısını desteklemiyor. Ayarlar\'da "Tahta aracı" seçeneğini kapatın.');
        throw new Error('Ollama hatası (' + r.status + '): ' + t.slice(0, 200));
      }
      const j = await r.json();
      return {
        text: (j.message && j.message.content) || '', toolInput: toolCalls(j.message), model: j.model || model,
        stop: j.done_reason || 'stop',
        usage: { input: j.prompt_eval_count || 0, output: j.eval_count || 0 }
      };
    }
  });
})(window.AT = window.AT || {});
