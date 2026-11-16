import test from 'node:test';
import assert from 'node:assert/strict';
import { yukle } from './yukle.mjs';

const AT = yukle('js/core.js');

test('splitCues: {n} işaretleri anlatımı parçalara böler', () => {
  assert.deepEqual(AT.splitCues('Giriş. {1}Vurgu. {2}Son.'), [
    { cue: 0, text: 'Giriş.' },
    { cue: 1, text: 'Vurgu.' },
    { cue: 2, text: 'Son.' }
  ]);
});

test('splitCues: işaretsiz ve boş metin tek parça döner', () => {
  assert.deepEqual(AT.splitCues('Düz anlatım.'), [{ cue: 0, text: 'Düz anlatım.' }]);
  assert.deepEqual(AT.splitCues(undefined), [{ cue: 0, text: '' }]);
});
