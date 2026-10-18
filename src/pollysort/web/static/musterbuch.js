/* Musterbuch — füllt die Stil-Tafel aus pixel.js und führt die Animationen vor. */
(function () {
  'use strict';
  const P = window.Pixel;
  const $ = (s) => document.querySelector(s);

  const FARBEN = [
    ['f-bg', 'Hintergrund', '--bg', 'Wachs-Creme / Nacht-Holz'],
    ['f-flaeche', 'Fläche', '--flaeche', 'Karten, Kopf- und Fußzeile'],
    ['f-flaeche-2', 'Fläche 2', '--flaeche-2', 'Zeilen-Hover, leere Zellen'],
    ['f-text', 'Text', '--text', 'Fließtext, Umrisse'],
    ['f-leise', 'Leise', '--leise', 'Unterzeilen, Hinweise'],
    ['f-honig-flaeche', 'Honig (Fläche)', '--honig-flaeche', 'Hauptknopf, gefüllte Zellen'],
    ['f-honig', 'Honig (Text)', '--honig', 'Erfolg — „Sauber sortiert"'],
    ['f-bluete', 'Blütenrosa', '--bluete', 'In Arbeit, Vorschau'],
    ['f-frage', 'Orange', '--frage', 'Rückfrage, Deadline bald'],
    ['f-fehler', 'Rot', '--fehler', 'Fehler, endgültig löschen'],
    ['f-wache', 'Grün', '--wache', 'Wache aktiv, Lernen'],
    ['f-linie', 'Linie', '--linie', 'Pixel-Rahmen, harter Schatten'],
  ];

  const SPRITES = [
    ['biene', 'Spurbiene', 'Sortierlauf, Logo, Statusleiste'],
    ['schlaf', 'Schlafende Biene', 'Eingang leer — alles aufgeräumt'],
    ['krone', 'Königin', 'Schwarm, Abzeichen „Weise Königin"'],
    ['lupe', 'Spähbiene', 'Vorschau, Waben-Vorschlag, Scan'],
    ['hammer', 'Baubiene', 'Wabenbau, Werkstatt'],
    ['glocke', 'Wächterbiene', 'Deadlines, Flugrouten'],
    ['topf', 'Sammelbiene', 'Honig = Erfolg, gelernte Ablageorte'],
    ['haus', 'Zuhause', 'Übersicht'],
    ['flugloch', 'Flugloch', 'Eingang & Sortieren'],
    ['frage', 'Rückfrage', 'Unsichere Fälle'],
    ['wabe', 'Wabe', 'Kategorie, Abzeichen „Erste Wabe"'],
    ['tafel', 'Wachstafel', 'Gelernte Regeln'],
    ['kiste', 'Quarantäne', 'Aussortiertes — nichts gelöscht'],
    ['rueckflug', 'Rückflug', 'Letzte Verschiebung zurück'],
    ['kalender', 'Bienen-Kalender', 'Deadlines, .ics'],
    ['auge', 'Auge der Biene', 'Datei mit dem Standardprogramm ansehen'],
    ['blitz', 'Tempo', 'Ultra Swarm, „sortiert mit" (BeeNara)'],
    ['warnung', 'Warnung', 'Fehler, Datei nicht lesbar, Rückfall'],
    ['haken', 'Erledigt', 'Stock-Check ok, Wache aktiv, eingerichtet'],
    ['kreuz', 'Fehlgeschlagen', 'Stock-Check-Fehler'],
    ['schluessel', 'Nektar-Quelle', 'OpenRouter-Schlüssel'],
    ['route', 'Flugroute', 'Discord, E-Mail, Benachrichtigungen'],
    ['gehirn', 'Gedächtnis', 'Lernen, Vorwärmen, Neuaufbau'],
    ['ordner', 'Ordner', 'Projekt, Unterordner'],
    ['laden', 'Herunterladen', 'BeeNara-Modell holen'],
    ['chip', 'Grafikkarte', 'GPU, lokales Modell'],
    ['zahnrad', 'Technik', 'Stock-Check, Darstellung'],
    ['weiche', 'Modellwahl', 'BeeNara oder BeeNara Big'],
    ['eimer', 'Entfernen', 'heruntergeladenes Modell löschen'],
    ['stift', 'Lehrmeister', 'Erste Korrektur beigebracht'],
    ['funkeln', 'Blitzblank', 'Eingang komplett leer'],
    ['sonne', 'Sieben Tage Sonne', '7 Tage in Folge aufgeräumt'],
    ['blume', 'Bunter Stock', '6 verschiedene Waben gefüllt'],
  ];

  const ABZEICHEN = [
    ['wabe', 'Erste Wabe', 'erstes Dokument einsortiert', true],
    ['10', 'Zehnerpack', '10 Dokumente einsortiert', true],
    ['100', 'Hundertschaft', '100 Dokumente einsortiert', false],
    ['stift', 'Lehrmeister', 'erste Korrektur beigebracht', true],
    ['krone', 'Weise Königin', '5 gelernte Regeln auf der Wachstafel', false],
    ['funkeln', 'Blitzblank', 'Posteingang komplett leer geräumt', true],
    ['sonne', 'Sieben Tage Sonne', '7 Tage in Folge aufgeräumt', false],
    ['blume', 'Bunter Stock', '6 verschiedene Waben gefüllt', false],
  ];

  const plakette = (inhalt) => {
    const innen = /^\d+$/.test(inhalt) ? `<span data-px="${inhalt}">${inhalt}</span>` : P.sprite(inhalt);
    return `<span class="plakette"><span>${innen}</span></span>`;
  };

  function aufbauen() {
    $('#mb-logo').innerHTML = P.biene('flattert') + '<span class="logo-wort" data-px="PollySort">PollySort</span>';
    $('#mb-farben').innerHTML = FARBEN.map(([k, name, token, wofuer]) =>
      `<div class="mb-farbe"><div class="muster ${k}">Aa</div><div class="info"><b>${name}</b><br><code>${token}</code><br><span class="leise">${wofuer}</span></div></div>`).join('');
    $('#mb-sprites').innerHTML = SPRITES.map(([n, name, wofuer]) =>
      `<div class="mb-sprite">${n === 'biene' ? P.biene('flattert') : P.sprite(n)}<b>${n}</b><span>${name}</span><small>${wofuer}</small></div>`).join('');
    $('#mb-zellen').innerHTML = [0, 0.25, 0.5, 0.75, 1].map((a) => `<span class="mb-sprite">${P.zelle(a)}<small>${Math.round(a * 100)} %</small></span>`).join('');
    let balken = '';
    for (let i = 0; i < 18; i++) balken += P.zelle(i < 11 ? 1 : 0);
    $('#mb-balken').innerHTML = `<div class="wabenbalken">${balken}</div><p class="hinweis">Wabenbalken: Fortschritt eines Laufs und der Stufe — 11 von 18 Zellen gefüllt.</p>`;
    const nav = (sprite, biene, klar, zahl) => `${P.sprite(sprite)}<span class="begriffe"><span class="biene-wort">${biene}</span><span class="klar">${klar}</span></span>${zahl ? `<span class="zaehler frage">${zahl}</span>` : '<span></span>'}`;
    $('#mb-nav-1').innerHTML = nav('wabe', 'Waben', 'Kategorien');
    $('#mb-nav-2').innerHTML = nav('frage', 'Rückfragen', 'Unsichere Fälle', 3);
    $('#mb-abzeichen').innerHTML = ABZEICHEN.map(([i, name, grund, ok]) =>
      `<div class="abzeichen ${ok ? 'verdient' : ''}">${plakette(i)}<b>${name}</b><small>${grund}</small></div>`).join('');
    $('#mb-flugloch').innerHTML = P.sprite('flugloch');
    $('#mb-wabe').innerHTML = P.sprite('wabe');
    $('#mb-schlaf').innerHTML = `<span>${P.sprite('schlaf')}<span class="schlaf-z">z</span></span><p>Keine losen Dateien. Alles aufgeräumt.</p>`;
    regeln(false);
    P.schrift(document);
  }

  function regeln(neu) {
    const r = [['telekom', 'Rechnungen'], ['mietvertrag', 'Verträge'], ['sitzung', 'Protokolle']];
    $('#mb-regeln').innerHTML = `<h3>${P.sprite('tafel')} Wachstafel</h3>` + r.map(([k, w]) =>
      `<div class="regel ${neu ? 'geritzt' : ''}"><span class="stichwort">${k}</span><span aria-hidden="true">→</span><b>${w}</b></div>`).join('');
    if (neu) document.querySelectorAll('#mb-regeln .regel').forEach((el, i) => el.style.setProperty('animation-delay', `${i * 0.12}s`));
  }

  const animVoll = () => document.documentElement.dataset.anim === 'voll' &&
    !window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  function mitte(el) {
    const r = el.getBoundingClientRect();
    return { x: r.left + r.width / 2, y: r.top + r.height / 2 };
  }

  function fliegen(geist) {
    if (!animVoll()) return;
    const a = mitte($('#mb-von'));
    const b = mitte($('#mb-nach'));
    for (let i = 0; i < 4; i++) {
      setTimeout(() => {
        const f = document.createElement('span');
        f.className = 'flieger' + (geist ? ' geist' : '');
        f.innerHTML = P.biene('flattert');
        $('#flugraum').appendChild(f);
        const hoch = Math.min(a.y, b.y) - 30 - Math.random() * 30;
        f.animate([
          { transform: `translate(${a.x - 14}px, ${a.y - 13}px)` },
          { transform: `translate(${(a.x + b.x) / 2 - 14}px, ${hoch}px)`, offset: 0.5 },
          { transform: `translate(${b.x - 14}px, ${b.y - 13}px)` },
        ], { duration: 950, easing: 'steps(16, end)' }).finished.then(() => f.remove());
      }, i * 180);
    }
  }

  function funkeln(el) {
    if (!animVoll()) return;
    const m = mitte(el);
    for (let i = 0; i < 9; i++) {
      const f = document.createElement('span');
      f.className = 'funke';
      f.innerHTML = P.sprite('funkeln');
      $('#flugraum').appendChild(f);
      const w = (Math.PI * 2 * i) / 9;
      const d = 40 + Math.random() * 40;
      f.animate([
        { transform: `translate(${m.x}px, ${m.y}px) scale(.4)`, opacity: 1 },
        { transform: `translate(${m.x + Math.cos(w) * d}px, ${m.y + Math.sin(w) * d}px) scale(1)`, opacity: 0 },
      ], { duration: 900, easing: 'steps(6, end)' }).finished.then(() => f.remove());
    }
  }

  function toast() {
    const el = document.createElement('div');
    el.className = 'toast erfolg';
    el.innerHTML = `${plakette('stift')}<div><b>Neues Abzeichen: Lehrmeister</b><span>erste Korrektur beigebracht</span></div><button class="zu" type="button" aria-label="Schließen">×</button>`;
    $('#hinweise').appendChild(el);
    el.querySelector('.zu').addEventListener('click', () => el.remove());
    setTimeout(() => el.remove(), 5500);
  }

  document.addEventListener('click', (ev) => {
    const thema = ev.target.closest('[data-mb-thema]');
    const anim = ev.target.closest('[data-mb-anim]');
    const demo = ev.target.closest('[data-mb]');
    if (thema) {
      document.documentElement.dataset.theme = thema.dataset.mbThema;
      document.querySelectorAll('[data-mb-thema]').forEach((b) => b.setAttribute('aria-pressed', String(b === thema)));
    }
    if (anim) {
      document.documentElement.dataset.anim = anim.dataset.mbAnim;
      document.querySelectorAll('[data-mb-anim]').forEach((b) => b.setAttribute('aria-pressed', String(b === anim)));
    }
    if (!demo) return;
    const was = demo.dataset.mb;
    if (was === 'flug') fliegen(false);
    if (was === 'geist') fliegen(true);
    if (was === 'funkeln') funkeln(demo);
    if (was === 'ritzen') regeln(true);
    if (was === 'toast') toast();
    if (was === 'glocke') {
      const g = $('#mb-sprites .sprite-glocke');
      g.classList.remove('wackeln');
      void g.getBoundingClientRect();
      if (document.documentElement.dataset.anim === 'voll') g.classList.add('wackeln');
      g.scrollIntoView({ block: 'center' });
    }
  });

  aufbauen();
})();
