/* Node testleri için bellekte duran Cache Storage ve sayfa adresi. Dönen Map: önbellek adı → (adres → Response). */
export function sahteDepo() {
  const depolar = new Map();
  const adres = (i) => (typeof i === 'string' ? i : i.url);
  const ac = (m) => ({
    put: async (i, y) => { m.set(adres(i), y); },
    match: async (i) => { const y = m.get(adres(i)); return y && y.clone(); },
    keys: async () => [...m.keys()].map((url) => ({ url })),
    delete: async (i) => m.delete(adres(i))
  });
  globalThis.caches = {
    open: async (ad) => { if (!depolar.has(ad)) depolar.set(ad, new Map()); return ac(depolar.get(ad)); },
    has: async (ad) => depolar.has(ad),
    delete: async (ad) => depolar.delete(ad),
    keys: async () => [...depolar.keys()]
  };
  globalThis.document = { baseURI: 'https://ornek.test/kk/' };
  return depolar;
}
