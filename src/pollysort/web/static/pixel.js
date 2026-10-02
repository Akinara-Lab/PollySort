/* PollySort · Flugbrett — Pixel-Schrift („Wabenschrift") und Pixel-Sprites.
 *
 * Alles hier ist selbst gezeichnet: keine Fremd-Schrift, kein Bild-Download, keine Lizenz-
 * fragen. Glyphen und Sprites sind Textraster ('#' bzw. Farbbuchstaben) und werden zu SVG
 * mit `shape-rendering: crispEdges` — gestochen scharf in jeder Größe und in beiden Themen,
 * weil die Farben aus CSS-Variablen kommen.
 */
(function () {
  'use strict';

  // ------------------------------------------------------------------ //
  //  Wabenschrift — 5×7, Großbuchstaben (Retro-Konsolen-Stil)
  // ------------------------------------------------------------------ //
  const G = {
    A: '.###.|#...#|#...#|#####|#...#|#...#|#...#',
    B: '####.|#...#|#...#|####.|#...#|#...#|####.',
    C: '.###.|#...#|#....|#....|#....|#...#|.###.',
    D: '####.|#...#|#...#|#...#|#...#|#...#|####.',
    E: '#####|#....|#....|####.|#....|#....|#####',
    F: '#####|#....|#....|####.|#....|#....|#....',
    G: '.###.|#...#|#....|#.###|#...#|#...#|.####',
    H: '#...#|#...#|#...#|#####|#...#|#...#|#...#',
    I: '###|.#.|.#.|.#.|.#.|.#.|###',
    J: '..###|...#.|...#.|...#.|...#.|#..#.|.##..',
    K: '#...#|#..#.|#.#..|##...|#.#..|#..#.|#...#',
    L: '#....|#....|#....|#....|#....|#....|#####',
    M: '#...#|##.##|#.#.#|#.#.#|#...#|#...#|#...#',
    N: '#...#|#...#|##..#|#.#.#|#..##|#...#|#...#',
    O: '.###.|#...#|#...#|#...#|#...#|#...#|.###.',
    P: '####.|#...#|#...#|####.|#....|#....|#....',
    Q: '.###.|#...#|#...#|#...#|#.#.#|#..#.|.##.#',
    R: '####.|#...#|#...#|####.|#.#..|#..#.|#...#',
    S: '.####|#....|#....|.###.|....#|....#|####.',
    T: '#####|..#..|..#..|..#..|..#..|..#..|..#..',
    U: '#...#|#...#|#...#|#...#|#...#|#...#|.###.',
    V: '#...#|#...#|#...#|#...#|#...#|.#.#.|..#..',
    W: '#...#|#...#|#...#|#.#.#|#.#.#|#.#.#|.#.#.',
    X: '#...#|#...#|.#.#.|..#..|.#.#.|#...#|#...#',
    Y: '#...#|#...#|.#.#.|..#..|..#..|..#..|..#..',
    Z: '#####|....#|...#.|..#..|.#...|#....|#####',
    'Ä': '.#.#.|.....|.###.|#...#|#...#|#####|#...#|#...#|#...#',
    'Ö': '.#.#.|.....|.###.|#...#|#...#|#...#|#...#|#...#|.###.',
    'Ü': '.#.#.|.....|#...#|#...#|#...#|#...#|#...#|#...#|.###.',
    0: '.###.|#...#|#..##|#.#.#|##..#|#...#|.###.',
    1: '..#..|.##..|..#..|..#..|..#..|..#..|.###.',
    2: '.###.|#...#|....#|...#.|..#..|.#...|#####',
    3: '####.|....#|....#|.###.|....#|....#|####.',
    4: '...#.|..##.|.#.#.|#..#.|#####|...#.|...#.',
    5: '#####|#....|####.|....#|....#|#...#|.###.',
    6: '..##.|.#...|#....|####.|#...#|#...#|.###.',
    7: '#####|....#|...#.|..#..|.#...|.#...|.#...',
    8: '.###.|#...#|#...#|.###.|#...#|#...#|.###.',
    9: '.###.|#...#|#...#|.####|....#|...#.|.##..',
    ' ': '...|...|...|...|...|...|...',
    '.': '.|.|.|.|.|.|#',
    ',': '..|..|..|..|..|.#|#.',
    ':': '.|.|#|.|.|#|.',
    ';': '..|..|.#|..|..|.#|#.',
    '!': '#|#|#|#|#|.|#',
    '?': '.###.|#...#|....#|...#.|..#..|.....|..#..',
    '-': '....|....|....|####|....|....|....',
    '+': '.....|..#..|..#..|#####|..#..|..#..|.....',
    '=': '.....|.....|#####|.....|#####|.....|.....',
    '/': '....#|....#|...#.|..#..|.#...|#....|#....',
    '(': '..#|.#.|#..|#..|#..|.#.|..#',
    ')': '#..|.#.|..#|..#|..#|.#.|#..',
    "'": '#|#|.|.|.|.|.',
    '"': '#.#|#.#|...|...|...|...|...',
    '%': '##..#|##..#|...#.|..#..|.#...|#..##|#..##',
    '&': '.##..|#..#.|#.#..|.#...|#.#.#|#..#.|.##.#',
    '·': '.|.|.|#|.|.|.',
    '→': '.....|..#..|...#.|#####|...#.|..#..|.....',
    '←': '.....|..#..|.#...|#####|.#...|..#..|.....',
    '…': '.....|.....|.....|.....|.....|.....|#.#.#',
    '_': '.....|.....|.....|.....|.....|.....|#####',
    '#': '.#.#.|#####|.#.#.|.#.#.|.#.#.|#####|.#.#.',
    '<': '...#|..#.|.#..|#...|.#..|..#.|...#',
    '>': '#...|.#..|..#.|...#|..#.|.#..|#...',
  };
  const GLYPHEN = {};
  for (const [k, v] of Object.entries(G)) GLYPHEN[k] = v.split('|');

  function glyphe(ch) {
    // toLocaleUpperCase macht aus ß ein SS — daher kann ein Zeichen zwei Glyphen ergeben.
    return Array.from(ch.toLocaleUpperCase('de-DE')).map((c) => {
      if (GLYPHEN[c]) return GLYPHEN[c];
      // Akzente & Exoten auf den Grundbuchstaben zurückführen — nie ein Loch im Wort.
      const basis = c.normalize('NFD').replace(/[̀-ͯ]/g, '');
      return GLYPHEN[basis] || GLYPHEN['?'];
    });
  }

  /** Ein Wort als SVG-Pfad (Höhe 7 Raster-Pixel). */
  function wortSvg(wort) {
    let x = 0;
    let d = '';
    for (const ch of Array.from(wort)) {
      for (const g of glyphe(ch)) {
        const breite = g[0].length;
        const oben = g.length - 7;          // 9 Zeilen = Umlaut: Punkte + Lücke über der Versalhöhe
        g.forEach((zeile, y) => {
          for (let i = 0; i < zeile.length; i++) {
            if (zeile[i] === '#') d += `M${x + i} ${y - oben}h1v1h-1z`;
          }
        });
        x += breite + 1;
      }
    }
    const w = Math.max(1, x - 1);
    return `<svg class="px-wort" viewBox="0 0 ${w} 7" width="${w}" height="7" aria-hidden="true" ` +
      `focusable="false" shape-rendering="crispEdges"><path fill="currentColor" d="${d}"/></svg>`;
  }

  function esc(s) {
    return String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  }

  /** Text in Pixel-Schrift: ein SVG je Wort (so darf eine Überschrift umbrechen). */
  function text(t) {
    const woerter = String(t).trim().split(/\s+/).filter(Boolean);
    return `<span class="sr-only">${esc(t)}</span><span class="px-text" aria-hidden="true">` +
      woerter.map(wortSvg).join('<span class="px-luecke"> </span>') + '</span>';
  }

  /** Alle Elemente mit `data-px` in Pixel-Schrift setzen (Text bleibt für Screenreader da). */
  function schrift(wurzel) {
    (wurzel || document).querySelectorAll('[data-px]').forEach((el) => {
      const t = el.getAttribute('data-px') || el.textContent;
      if (el.dataset.pxFertig === t) return;
      el.innerHTML = text(t);
      el.dataset.pxFertig = t;
    });
  }

  // ------------------------------------------------------------------ //
  //  Sprites — Farbbuchstaben → CSS-Klassen (.sp-k, .sp-y …), siehe app.css
  // ------------------------------------------------------------------ //
  const S = {
    biene: [
      '....ll.ll.....',
      '...lwwlwwl....',
      '...lwwlwwl....',
      '....lllll.....',
      '...kkkkkkkk...',
      '..kyydyydyykk.',
      'kkyyydyydyykhk',
      '..koodyodyokk.',
      '...kkkkkkkk...',
      '....k..k......',
    ],
    biene2: [
      '..............',
      '...lll.lll....',
      '..lwwwlwwwl...',
      '...lllllll....',
      '...kkkkkkkk...',
      '..kyydyydyykk.',
      'kkyyydyydyykhk',
      '..koodyodyokk.',
      '...kkkkkkkk...',
      '.....k..k.....',
    ],
    schlaf: [
      '..............',
      '..............',
      '...lll.lll....',
      '..lwwwlwwwl...',
      '...kkkkkkkk...',
      '..kyydyydyykk.',
      'kkyyydyydyykkk',
      '..koodyodyokk.',
      '...kkkkkkkk...',
      '..............',
    ],
    haus: [
      '.....kk.....',
      '....kook....',
      '...kooook...',
      '..kooooook..',
      '.kooooooook.',
      'kkkkkkkkkkkk',
      '.kcccccccck.',
      '.kcckkkkcck.',
      '.kcck..kcck.',
      '.kcck..kcck.',
      '.kcck..kcck.',
      '.kkkkkkkkkk.',
    ],
    flugloch: [
      '............',
      '....kkkk....',
      '..kkyyyykk..',
      '.kyyyyyyyyk.',
      '.kooooooook.',
      'kyyyyyyyyyyk',
      'kooooooooook',
      'kyyyykkyyyyk',
      'kyyyk..kyyyk',
      'koook..koook',
      'kkkkkkkkkkkk',
      '.kk......kk.',
    ],
    frage: [
      '.kkkkkkkkkk.',
      'kffffkkffffk',
      'kfffkffkfffk',
      'kffffffkfffk',
      'kfffffkffffk',
      'kffffkfffffk',
      'kffffffffffk',
      'kffffkfffffk',
      '.kkkkkkkkkk.',
      '...kfk......',
      '..kfk.......',
      '..kk........',
    ],
    wabe: [
      '...kkkkkk...',
      '..kyyyyyyk..',
      '.kyhyyyyyyk.',
      'kyhyyyyyyyyk',
      'kyyyyyyyyyyk',
      'kyyyyyyyyyyk',
      'kyyyyyyyyyyk',
      'kyyyyyyyyyok',
      'kyyyyyyyyook',
      '.kyyyyyyook.',
      '..kooooook..',
      '...kkkkkk...',
    ],
    krone: [
      '............',
      '............',
      'k....kk....k',
      'kk..kyyk..kk',
      'kyk.kyyk.kyk',
      'kyykyyyykyyk',
      'kyyyyyyyyyyk',
      'kyyryyyyryyk',
      'kyyyyyyyyyyk',
      'kooooooooook',
      'kkkkkkkkkkkk',
      '............',
    ],
    tafel: [
      '............',
      'kkkkkkkkkkkk',
      'kbbbbbbbbbbk',
      'kboooooooobk',
      'kbokkkkkoobk',
      'kboooooooobk',
      'kbokkkkkkobk',
      'kboooooooobk',
      'kbokkkoooobk',
      'kboooooooobk',
      'kbbbbbbbbbbk',
      'kkkkkkkkkkkk',
    ],
    kiste: [
      '............',
      '.kkkkkkkkkk.',
      '.kbbbbbbbbk.',
      'kkkkkkkkkkkk',
      'kbbbbbbbbbbk',
      'kbbkbbbbkbbk',
      'kbbbkbbkbbbk',
      'kbbbbkkbbbbk',
      'kbbbkbbkbbbk',
      'kbbkbbbbkbbk',
      'kbbbbbbbbbbk',
      'kkkkkkkkkkkk',
    ],
    hammer: [
      '............',
      '.kkkkkkkkk..',
      'kmmmmmmmmmk.',
      'kmhmmmmmmmmk',
      '.kkkkbbkkkk.',
      '....kbbk....',
      '....kbbk....',
      '....kbbk....',
      '....kbbk....',
      '....kbbk....',
      '....kbbk....',
      '....kkkk....',
    ],
    glocke: [
      '.....kk.....',
      '....kyyk....',
      '...kyyyyk...',
      '..kyyhyyyk..',
      '..kyhyyyyk..',
      '..kyyyyyyk..',
      '..kyyyyyok..',
      '.kyyyyyyyok.',
      'kyyyyyyyyook',
      'kkkkkkkkkkkk',
      '.....kk.....',
      '............',
    ],
    topf: [
      '............',
      '..kkkkkkkk..',
      '..kcccccck..',
      '.kkkkkkkkkk.',
      'kooyyyyyyook',
      'koyyyhyyyyok',
      'koyyhyyyyyok',
      'koyyyyyyyyok',
      'kooyyyyyyook',
      '.kooooooook.',
      '..kkkkkkkk..',
      '............',
    ],
    lupe: [
      '...kkkk.....',
      '..kwwwwk....',
      '.kwhwwwwk...',
      '.kwhwwwwk...',
      '.kwwwwwwk...',
      '.kwwwwwwk...',
      '..kwwwwk....',
      '...kkkkk....',
      '.......kbk..',
      '........kbk.',
      '.........kbk',
      '..........k.',
    ],
    rueckflug: [
      '............',
      '...k........',
      '..kyk.......',
      '.kyyykkkkk..',
      'kyyyyyyyyyk.',
      '.kyyykkkkyyk',
      '..kyk....kyk',
      '...k.....kyk',
      '.........kyk',
      '....kkkkkyyk',
      '....kyyyyyk.',
      '....kkkkkk..',
    ],
    kalender: [
      '..kk....kk..',
      'kkkkkkkkkkkk',
      'krrrrrrrrrrk',
      'kkkkkkkkkkkk',
      'kcccccccccck',
      'kckckckckcck',
      'kcccccccccck',
      'kckckckckcck',
      'kcccccccccck',
      'kckckcccccck',
      'kcccccccccck',
      'kkkkkkkkkkkk',
    ],
    funkeln: [
      '...y...',
      '...y...',
      '..yhy..',
      'yyhhhyy',
      '..yhy..',
      '...y...',
      '...y...',
    ],
    blume: [
      '..pp.pp..',
      '.ppppppp.',
      '.ppyyypp.',
      '..pyyyp..',
      '.ppyyypp.',
      '.ppppppp.',
      '..pp.pp..',
      '....g....',
      '...ggg...',
    ],
    sonne: [
      '.....y.....',
      '.y...y...y.',
      '..y.....y..',
      '....yyy....',
      '...yyhyy...',
      'yy.yyyyy.yy',
      '...yyyyy...',
      '....yyy....',
      '..y.....y..',
      '.y...y...y.',
      '.....y.....',
    ],
    stift: [
      '.........kk.',
      '........kppk',
      '.......kyypk',
      '......kyyyk.',
      '.....kyyyk..',
      '....kyyyk...',
      '...kyyyk....',
      '..kcyyk.....',
      '.kccck......',
      '.kkck.......',
      'kkk.........',
      '............',
    ],
    blitz: [
      '......kkk...',
      '.....kyyk...',
      '....kyyk....',
      '...kyyk.....',
      '..kyyykkkk..',
      '..kyyyyyyk..',
      '..kkkkyyk...',
      '.....kyk....',
      '....kyk.....',
      '...kyk......',
      '...kk.......',
      '............',
    ],
    auge: [
      '............',
      '............',
      '...kkkkkk...',
      '.kkcccccckk.',
      'kccckkkkccck',
      'kcckkhkkkcck',
      'kccckkkkccck',
      '.kkcccccckk.',
      '...kkkkkk...',
      '............',
      '............',
      '............',
    ],
  };

  function spriteSvg(name, klasse) {
    const raster = S[name];
    if (!raster) return '';
    const h = raster.length;
    const w = Math.max(...raster.map((z) => z.length));
    const pfade = {};
    raster.forEach((zeile, y) => {
      for (let x = 0; x < zeile.length; x++) {
        const c = zeile[x];
        if (c === '.' || c === ' ') continue;
        pfade[c] = (pfade[c] || '') + `M${x} ${y}h1v1h-1z`;
      }
    });
    const inhalt = Object.entries(pfade).map(([c, d]) => `<path class="sp-${c}" d="${d}"/>`).join('');
    return `<svg class="sprite sprite-${name} ${klasse || ''}" viewBox="0 0 ${w} ${h}" width="${w}" ` +
      `height="${h}" aria-hidden="true" focusable="false" shape-rendering="crispEdges">${inhalt}</svg>`;
  }

  /** Die fliegende Biene: zwei Flügel-Phasen übereinander, CSS wechselt sie im Takt. */
  function biene(klasse) {
    return `<span class="biene ${klasse || ''}" aria-hidden="true">` +
      spriteSvg('biene', 'phase-a') + spriteSvg('biene2', 'phase-b') + '</span>';
  }

  // ------------------------------------------------------------------ //
  //  Wabenzelle mit Füllstand — pixeliges Sechseck, Honig steigt von unten
  // ------------------------------------------------------------------ //
  const ZELLE = [
    '....kkkkkk....',
    '...kxxxxxxk...',
    '..kxxxxxxxxk..',
    '.kxxxxxxxxxxk.',
    'kxxxxxxxxxxxxk',
    'kxxxxxxxxxxxxk',
    'kxxxxxxxxxxxxk',
    'kxxxxxxxxxxxxk',
    'kxxxxxxxxxxxxk',
    'kxxxxxxxxxxxxk',
    '.kxxxxxxxxxxk.',
    '..kxxxxxxxxk..',
    '...kxxxxxxk...',
    '....kkkkkk....',
  ];

  function zelle(anteil, klasse) {
    const h = ZELLE.length;
    const w = ZELLE[0].length;
    const voll = Math.round(Math.max(0, Math.min(1, anteil || 0)) * (h - 2));
    let rand = '';
    let leer = '';
    let honig = '';
    let glanz = '';
    ZELLE.forEach((zeile, y) => {
      for (let x = 0; x < w; x++) {
        const c = zeile[x];
        const r = `M${x} ${y}h1v1h-1z`;
        if (c === 'k') rand += r;
        else if (c === 'x') {
          if (h - 1 - y <= voll) {
            if (x === 3 && h - 1 - y === voll) glanz += r; else honig += r;
          } else leer += r;
        }
      }
    });
    return `<svg class="zelle ${klasse || ''}" viewBox="0 0 ${w} ${h}" width="${w}" height="${h}" ` +
      `aria-hidden="true" focusable="false" shape-rendering="crispEdges">` +
      `<path class="z-leer" d="${leer}"/><path class="z-honig" d="${honig}"/>` +
      `<path class="z-glanz" d="${glanz}"/><path class="z-rand" d="${rand}"/></svg>`;
  }

  window.Pixel = { text, schrift, sprite: spriteSvg, biene, zelle, SPRITES: Object.keys(S) };
})();
