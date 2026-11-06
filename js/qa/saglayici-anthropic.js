/* Sağlayıcı: Anthropic Claude API (bulut). Anahtarı kullanıcı girer; yalnız bu tarayıcıda saklanır.
 * Resmî SDK (vendor/anthropic-sdk.js, MIT) ilk soruda yüklenir; model kipi kapalıyken hiç yüklenmez.
 * Sabit sistem metni önbelleğe alınır: aynı derste ikinci sorudan itibaren o kısım ~%95 ucuzlar. */
(function (AT) {
  'use strict';

  const ROOT = new URL('../../', document.currentScript.src).href;
  let sdk = null;
  const load = () => (sdk = sdk || import(ROOT + 'vendor/anthropic-sdk.js'));

  // Kullanıcıya anlaşılır hata iletileri.
  function explain(e, mod) {
    if (mod && e instanceof mod.AuthenticationError) return new Error('API anahtarı geçersiz. Ayarlar\'dan yeniden girin.');
    if (mod && e instanceof mod.PermissionDeniedError) return new Error('Bu anahtarın bu modele erişim izni yok.');
    if (mod && e instanceof mod.RateLimitError) return new Error('Çok sık soru soruldu ya da hesap sınırına ulaşıldı. Biraz bekleyip yeniden deneyin.');
    if (mod && e instanceof mod.APIConnectionError) return new Error('Claude API\'ye ulaşılamadı. İnternet bağlantısını denetleyin.');
    if (mod && e instanceof mod.APIError) return new Error('Claude API hatası (' + (e.status || '?') + '): ' + (e.message || ''));
    return e;
  }

  AT.qa.registerProvider('anthropic', {
    label: 'Claude (Anthropic API)',
    kind: 'api',
    needsKey: true,
    defaultModel: 'claude-opus-5-5',
    models: ['claude-opus-5-5', 'claude-sonnet-5-5', 'claude-haiku-5-5'],
    tools: true,

    async chat({ system, messages, tools, onText, signal, model, baseURL, key }) {
      const mod = await load();
      const client = new mod.Anthropic({ apiKey: key, baseURL: baseURL || undefined, dangerouslyAllowBrowser: true, maxRetries: 1 });
      const params = {
        model,
        max_tokens: 4000,
        system: [{ type: 'text', text: system, cache_control: { type: 'ephemeral' } }],
        messages,
        output_config: { effort: 'low' }
      };
      if (tools.length) {
        params.tools = tools.map((t) => ({ name: t.name, description: t.description, input_schema: t.parameters, eager_input_streaming: true }));
        params.tool_choice = { type: 'auto' };
      }
      // Güvenlik sınıflandırıcısı reddederse istek sunucuda yedek modelle sürer (Haiku'da yok).
      if (!/haiku/.test(model)) { params.betas = ['server-side-fallback-2026-07-01']; params.fallbacks = 'default'; }

      let text = '';
      let msg;
      try {
        const stream = client.beta.messages.stream(params, { signal });
        stream.on('text', (d) => { text += d; if (onText) onText(text); });
        msg = await stream.finalMessage();
      } catch (e) { throw explain(e, mod); }

      if (msg.stop_reason === 'refusal') throw new Error('Model bu soruyu yanıtlamayı reddetti. Soruyu ders konusuna göre yeniden yazmayı deneyin.');
      text = msg.content.filter((b) => b.type === 'text').map((b) => b.text).join('');
      // Akışta kesilmiş araç girdisi gelebilir; ancak düzgün bir nesneyse kullanılır.
      let toolInput = null;
      if (msg.stop_reason !== 'max_tokens') {
        const tu = msg.content.find((b) => b.type === 'tool_use' && b.name === 'tahtaya_yaz');
        if (tu && tu.input && Array.isArray(tu.input.komutlar)) toolInput = tu.input;
      }
      const u = msg.usage || {};
      return {
        text, toolInput, model: msg.model || model, stop: msg.stop_reason,
        usage: { input: u.input_tokens || 0, output: u.output_tokens || 0, cacheRead: u.cache_read_input_tokens || 0, cacheWrite: u.cache_creation_input_tokens || 0 }
      };
    }
  });
})(window.AT = window.AT || {});
