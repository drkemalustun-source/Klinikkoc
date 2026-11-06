/* Bilgi bulma (KnowledgeRetriever). Canlı soru-cevapta modele yalnız burada bulunan parçalar verilir.
 *
 *   retriever.search(soru, { limit }) -> [{ id, kind, title, text, ref, license, open, stepId?, score }]
 *
 * İki uygulama var, sırayla sorulur:
 *   LessonRetriever : dersin kendi anlatımı, soruları ve alt hedefleri (her zaman var).
 *   IndexRetriever  : ders klasöründeki kaynak-dizini.json (tools/dizin-uret.py üretir).
 *                     Kurulum gerektirmez; arama tarayıcıda yapılır. İleride bir vektör
 *                     veritabanı aynı arayüzle (search) bu dosyanın yerine geçebilir.
 * Arama BM25 ile yapılır; Türkçe ekler için sözcüklerin ilk 6 harfi karşılaştırılır. */
(function (AT) {
  'use strict';

  const STOP = new Set(('ve veya ile da de bu şu o bir için gibi daha en çok ne mi mı mu mü ise ki ama ancak hem ya '
    + 'olan olarak olur olup oldu ol var yok nasıl neden niçin hangi hangisi kadar sonra önce göre her tüm bazı '
    + 'the of and or in on to a an is are for with by').split(' '));

  function tokens(text) {
    return String(text || '')
      .toLocaleLowerCase('tr-TR')
      .replace(/[’'`´]/g, ' ')
      .split(/[^\p{L}\p{N}.]+/u)
      .map((t) => t.replace(/^\.+|\.+$/g, ''))
      .filter((t) => t.length > 1 && !STOP.has(t))
      .map((t) => (/^\d/.test(t) ? t : t.slice(0, 6)));
  }

  // Basit BM25 dizini.
  class Bm25 {
    constructor(docs) {
      this.docs = docs;
      this.tf = docs.map((d) => {
        const m = new Map();
        for (const t of tokens(d.searchText || d.text)) m.set(t, (m.get(t) || 0) + 1);
        return m;
      });
      this.len = this.tf.map((m) => [...m.values()].reduce((a, b) => a + b, 0));
      this.avg = this.len.reduce((a, b) => a + b, 0) / Math.max(1, this.len.length);
      this.df = new Map();
      for (const m of this.tf) for (const t of m.keys()) this.df.set(t, (this.df.get(t) || 0) + 1);
    }

    search(query, limit = 5) {
      const q = [...new Set(tokens(query))];
      const N = this.docs.length, k1 = 1.2, b = 0.75;
      const out = [];
      this.tf.forEach((m, i) => {
        let s = 0;
        for (const t of q) {
          const f = m.get(t);
          if (!f) continue;
          const idf = Math.log(1 + (N - this.df.get(t) + 0.5) / (this.df.get(t) + 0.5));
          s += idf * (f * (k1 + 1)) / (f + k1 * (1 - b + b * this.len[i] / this.avg));
        }
        if (s > 0) out.push({ ...this.docs[i], score: s });
      });
      return out.sort((x, y) => y.score - x.score).slice(0, limit);
    }
  }

  // Dersin kendi metni: her anlatım adımı bir parça; sorular açıklamalarıyla birlikte.
  class LessonRetriever {
    constructor(lesson) {
      const license = (lesson.source && lesson.source.license) || '';
      const docs = [];
      lesson.sections.forEach((sec) => {
        for (const st of sec.steps) {
          const boardText = (st.board || []).map((c) => [c.text, c.term, c.definition, c.label, c.title,
            ...(c.items || []), ...(c.nodes || []), ...((c.rows || []).flat())].filter(Boolean).join(' ')).join(' ');
          if (st.say) {
            const text = AT.plainSay(st.say);
            docs.push({ id: 'ders:' + st.id, kind: 'ders', stepId: st.id, title: sec.title, text,
              searchText: sec.title + ' ' + text + ' ' + boardText, ref: st.sourceRef || '', license, open: true });
          }
          if (st.question) {
            const q = st.question;
            const right = (q.options || []).filter((o) => o.correct).map((o) => o.text.replace(/[.\s]+$/, '')).join('; ');
            const text = q.prompt + (right ? ' Doğru cevap: ' + right + '.' : '') + (q.explanation ? ' ' + q.explanation : '');
            docs.push({ id: 'ders:' + st.id, kind: 'soru', stepId: st.id, title: sec.title, text,
              ref: q.sourceRef || '', license, open: true });
          }
        }
      });
      this.index = new Bm25(docs);
    }
    search(query, opts = {}) { return this.index.search(query, opts.limit || 4); }
  }

  // "s. 2–3 · 2.1; s. 8 · Şekil 4" -> [2, 3, 8]
  function pagesOf(ref) {
    const out = new Set();
    for (const m of String(ref || '').matchAll(/s\.\s*(\d+)(?:\s*[–-]\s*(\d+))?/g)) {
      const a = Number(m[1]), b = Number(m[2] || m[1]);
      for (let p = a; p <= Math.min(b, a + 5); p++) out.add(p);
    }
    return out;
  }

  // Kurulumsuz kaynak dizini. Biçim (tools/dizin-uret.py):
  //   { kaynaklar: [{ id, baslik, kisa, atif, lisans, acik }], sozluk: { tr: en }, parcalar: [{ k: kaynak sırası, s: sayfa, t: metin }] }
  // Kaynak İngilizce olabilir: sözlük, Türkçe sorudaki terimlerin İngilizcesini aramaya ekler;
  // opts.pages (ders anlatımında bulunan yerlerin sayfaları) aynı sayfadaki parçaları öne çıkarır.
  class IndexRetriever {
    constructor(data) {
      this.sources = data.kaynaklar || [];
      this.glossary = Object.entries(data.sozluk || {}).map(([tr, en]) => ({ keys: tokens(tr), en }));
      this.docs = (data.parcalar || []).map((p, i) => {
        const src = this.sources[p.k] || {};
        return {
          id: 'kaynak:' + (src.id || p.k) + ':' + i, kind: 'kaynak', title: src.baslik || '', text: p.t, page: p.s,
          ref: (src.kisa || src.baslik || '') + (p.s ? ', s. ' + p.s : ''), license: src.lisans || '',
          open: !!src.acik, citation: src.atif || ''
        };
      });
      this.index = new Bm25(this.docs);
    }
    expand(query) {
      const q = new Set(tokens(query));
      const extra = this.glossary.filter((g) => g.keys.length && g.keys.every((k) => q.has(k))).map((g) => g.en);
      return query + ' ' + extra.join(' ');
    }
    search(query, opts = {}) {
      const limit = opts.limit || 4, pages = opts.pages || new Set();
      const hits = this.index.search(this.expand(query), 30);
      for (const h of hits) if (pages.has(h.page)) h.score *= 1.5;
      // Sözcük eşleşmesi yoksa ders anlatımının dayandığı sayfanın ilk parçası verilir.
      if (!hits.length && pages.size) {
        for (const d of this.docs) if (pages.has(d.page) && !hits.some((h) => h.page === d.page)) hits.push({ ...d, score: 0 });
      }
      return hits.sort((x, y) => y.score - x.score).slice(0, Math.max(2, Math.floor(limit / 2)));
    }
  }

  // Ders + dizin: önce ders, sonra kaynak; aynı metin iki kez verilmez.
  class KnowledgeRetriever {
    constructor(parts) { this.parts = parts; }
    search(query, opts = {}) {
      const seen = new Set(), out = [];
      const pages = new Set();
      for (const r of this.parts) {
        for (const hit of r.search(query, Object.assign({}, opts, { pages }))) {
          const key = hit.text.slice(0, 80);
          if (seen.has(key)) continue;
          seen.add(key);
          out.push(hit);
          if (hit.kind !== 'kaynak') for (const p of pagesOf(hit.ref)) pages.add(p);
        }
      }
      return out;
    }
  }

  // Ders için bilgi bulucuyu kur; kaynak dizini varsa yükle (yoksa yalnız ders).
  AT.createRetriever = async (lesson) => {
    const parts = [new LessonRetriever(lesson)];
    const path = (lesson.knowledge && lesson.knowledge.index) || 'kaynak-dizini.json';
    try {
      const data = await AT.loadLessonFile(lesson, path, lesson.id + ':dizin');
      if (data) parts.push(new IndexRetriever(data));
    } catch (e) { /* dizin yok: yalnız ders metni */ }
    return new KnowledgeRetriever(parts);
  };

  AT.bilgi = { tokens, pagesOf, Bm25, LessonRetriever, IndexRetriever, KnowledgeRetriever };
})(window.AT = window.AT || {});
