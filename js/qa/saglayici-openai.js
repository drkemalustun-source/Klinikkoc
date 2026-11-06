/* Sağlayıcı: OpenAI uyumlu sunucu (/chat/completions). LM Studio, llama.cpp sunucusu, vLLM
 * gibi yerel ya da fakülte sunucularında çalışan modeller için. Anahtar gerekiyorsa
 * yalnız bu tarayıcıda saklanır. */
(function (AT) {
  'use strict';

  function toolInput(msg) {
    for (const c of (msg && msg.tool_calls) || []) {
      const f = c.function || {};
      if (f.name !== 'tahtaya_yaz') continue;
      try {
        const a = typeof f.arguments === 'string' ? JSON.parse(f.arguments) : f.arguments;
        if (a && Array.isArray(a.komutlar)) return a;
      } catch (e) { /* bozuk JSON: tahta atlanır */ }
    }
    return null;
  }

  AT.qa.registerProvider('openai', {
    label: 'OpenAI uyumlu sunucu',
    kind: 'local',
    needsKey: false,
    optionalKey: true,
    defaultModel: '',
    defaultBaseURL: 'http://localhost:1234/v1',
    tools: true,

    async chat({ system, messages, tools, signal, model, baseURL }) {
      const key = AT.qa.getKey('openai');
      const body = { model, messages: [{ role: 'system', content: system }, ...messages], temperature: 0.2 };
      if (tools.length) {
        body.tools = tools.map((t) => ({ type: 'function', function: { name: t.name, description: t.description, parameters: t.parameters } }));
        body.tool_choice = 'auto';
      }
      const headers = { 'Content-Type': 'application/json' };
      if (key) headers.Authorization = 'Bearer ' + key;
      let r;
      try {
        r = await fetch(baseURL.replace(/\/+$/, '') + '/chat/completions', { method: 'POST', headers, body: JSON.stringify(body), signal });
      } catch (e) {
        if (e.name === 'AbortError') throw e;
        throw new Error('Sunucuya ulaşılamadı (' + baseURL + ').');
      }
      if (!r.ok) throw new Error('Sunucu hatası (' + r.status + '): ' + (await r.text().catch(() => '')).slice(0, 200));
      const j = await r.json();
      const ch = (j.choices && j.choices[0]) || {};
      const u = j.usage || {};
      return {
        text: (ch.message && ch.message.content) || '', toolInput: toolInput(ch.message), model: j.model || model,
        stop: ch.finish_reason,
        usage: { input: u.prompt_tokens || 0, output: u.completion_tokens || 0, cacheRead: (u.prompt_tokens_details && u.prompt_tokens_details.cached_tokens) || 0 }
      };
    }
  });
})(window.AT = window.AT || {});
