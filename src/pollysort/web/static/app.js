/* PollySort · Flugbrett — die Seite.
 *
 * Kein Framework, kein Build-Schritt, kein Fremd-Code: Die Seite holt Daten vom lokalen
 * Dienst (/api/…), baut daraus HTML und hört über einen Ereignisstrom mit, was die Bienen
 * gerade tun. Alles, was aus Dateien oder Dokumenten stammt, läuft durch `esc()`.
 *
 * Gamification in Maßen: Stufen und Abzeichen kommen ausschließlich aus spiel.py (echte
 * Arbeit), Animationen gibt es nur an den Stellen, an denen auch die Konsole reagiert —
 * und alles lässt sich auf „dezent" oder „aus" stellen (Arbeitsmodus).
 */
(function () {
  'use strict';

  const P = window.Pixel;
  const $ = (s, r) => (r || document).querySelector(s);
  const $$ = (s, r) => Array.from((r || document).querySelectorAll(s));
  const esc = (s) => String(s == null ? '' : s).replace(/[&<>"']/g,
    (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

  // ------------------------------------------------------------------ //
  //  Keine Emojis in der Oberfläche: Die Konsole schmückt ihre Meldungen mit Emojis
  //  (Honigtopf, Biene, Haken …). Im Flugbrett wird daraus das passende Pixel-Icon. Die Schlüssel
  //  stehen als Escapes, damit diese Datei selbst emoji-frei bleibt (ein Test prüft das).
  // ------------------------------------------------------------------ //
  const SYMBOL = {
    '\u{1F36F}': 'topf', '\u{1F4B8}': 'topf',                       // Honigtopf, Kosten
    '\u{1F41D}': 'biene',                                            // Biene
    '\u{1F338}': 'blume',                                            // Blüte (in Arbeit)
    '\u2753': 'frage',                                               // Rückfrage
    '\u26A0': 'warnung', '\u{1F6DF}': 'warnung', '\u{1F7E0}': 'warnung', // Warnung, Rettungsring
    '\u274C': 'kreuz', '\u{1F534}': 'kreuz',                        // nein, rot
    '\u2705': 'haken', '\u{1F7E2}': 'haken',                        // erledigt, grün
    '\u{1F389}': 'funkeln', '\u2728': 'funkeln', '\u{1F3C5}': 'funkeln', '\u{1F195}': 'funkeln',
    '\u{1F3C6}': 'krone', '\u{1F451}': 'krone',                     // Pokal, Königin
    '\u270D': 'stift',                                               // Nacherfassung
    '\u{1F9EA}': 'lupe', '\u{1F50E}': 'lupe', '\u{1F50D}': 'lupe', // Vorschau, Analyse
    '\u{1F440}': 'auge',                                             // Wache schaut
    '\u{1F9E0}': 'gehirn',                                           // Gedächtnis
    '\u{1F4DC}': 'tafel', '\u{1F4CB}': 'tafel',                     // Wachstafel, Bericht
    '\u21A9': 'rueckflug', '\u{1F501}': 'rueckflug', '\u{1F504}': 'rueckflug',
    '\u26B0': 'kiste', '\u{1F6E1}': 'kiste', '\u{1F5C4}': 'kiste', // Quarantäne, Dublette, Sicherung
    '\u{1F4C2}': 'ordner', '\u{1F4C1}': 'ordner', '\u{1F5C2}': 'ordner',
    '\u{1F6E0}': 'hammer',                                           // Baubienen
    '\u{1F4C5}': 'kalender', '\u23F1': 'kalender',                  // Kalender, Zeit
    '\u{1F514}': 'glocke',                                           // Wächterbienen
    '\u{1F9ED}': 'route', '\u{1F4E7}': 'route', '\u{1F3AE}': 'route', // Flugrouten, E-Mail, Discord
    '\u{1F4E5}': 'flugloch', '\u{1F4ED}': 'flugloch',               // Eingang
    '\u{1F3E0}': 'haus',
    '\u{1F511}': 'schluessel',                                       // Nektar-Quelle
    '\u26A1': 'blitz',                                               // Tempo, sortiert mit
    '\u{1F5A5}': 'chip', '\u{1F999}': 'chip',                       // Grafikkarte, Ollama
    '\u2699': 'zahnrad', '\u{1F3A8}': 'zahnrad',                    // Technik, Darstellung
    '\u{1F500}': 'weiche',                                           // Modellwahl
    '\u{1F5D1}': 'eimer',                                            // Modell entfernt
    '\u{1F4E6}': 'laden', '\u2B07': 'laden',                        // Paket, Download
    '\u{1F423}': 'wabe',                                             // neue Kategorie schlüpft
    '\u{1F30D}': 'zahnrad', '\u{1F310}': 'zahnrad', '\u{1FA7A}': 'zahnrad', // Sprache, Stock-Check
    '\u{1F578}': 'lupe',                                             // keine Treffer
    '\u{1F680}': 'blitz',                                            // Start, Tempo
    '\u{1F9F9}': 'eimer',                                            // aufräumen
    '\u{1F9FD}': 'tafel',                                            // Wachstafel abgewischt
  };
  const ART_SYMBOL = { honey: 'topf', error: 'warnung', ask: 'frage', bloom: 'blume', feier: 'funkeln', info: 'biene' };
  const PIKTOGRAMM = /[\p{Extended_Pictographic}\u{1F1E6}-\u{1F1FF}\uFE0F\u200D]/gu;

  /** Das Pixel-Icon zu einem Emoji der Konsole — sonst eins passend zur Meldungsart. */
  function symbol(emoji, art) {
    const name = SYMBOL[String(emoji || '').replace(/[\uFE0F\u200D]/g, '')] || ART_SYMBOL[art] || 'biene';
    return P.sprite(name, 'symbol');
  }

  /** Text ohne Emojis (Pfeile, Häkchen-Zeichen und Satzzeichen bleiben). */
  const ohneEmoji = (text) => String(text == null ? '' : text).replace(PIKTOGRAMM, '').replace(/ {2,}/g, ' ').trim();

  // ------------------------------------------------------------------ //
  //  Sitzungs-Token: kommt einmalig im Fragment (#t=…), dann nur noch im Speicher
  // ------------------------------------------------------------------ //
  const TOKEN = (() => {
    const m = location.hash.match(/[#&]t=([A-Za-z0-9_-]+)/);
    let tok = '';
    try { tok = sessionStorage.getItem('flugbrett-token') || ''; } catch (e) { /* privat */ }
    if (m) {
      tok = m[1];
      try { sessionStorage.setItem('flugbrett-token', tok); } catch (e) { /* privat */ }
      history.replaceState(null, '', location.pathname + '#/zuhause');
    }
    return tok;
  })();

  // ------------------------------------------------------------------ //
  //  API
  // ------------------------------------------------------------------ //
  class ApiFehler extends Error {
    constructor(text, status) { super(text); this.status = status; }
  }

  async function api(pfad, daten) {
    const opt = { headers: { 'X-Flugbrett-Token': TOKEN } };
    if (daten !== undefined) {
      opt.method = 'POST';
      opt.headers['Content-Type'] = 'application/json';
      opt.body = JSON.stringify(daten);
    }
    let antwort;
    try {
      antwort = await fetch('/api/' + pfad, opt);
    } catch (e) {
      throw new ApiFehler(t('web.err.offline'), 0);
    }
    let json = {};
    try { json = await antwort.json(); } catch (e) { /* leer */ }
    if (!antwort.ok) throw new ApiFehler(json.fehler || t('web.err.unknown'), antwort.status);
    return json;
  }
  const lesen = (name, params) => api(name + (params ? '?' + new URLSearchParams(params) : ''));
  const tun = async (name, daten) => (await api(name, daten || {})).ergebnis;

  // ------------------------------------------------------------------ //
  //  Texte (aus i18n.py — dieselben wie in der Konsole)
  // ------------------------------------------------------------------ //
  let T = {};
  function t(key, p) {
    let s = T[key];
    if (s == null) return key;
    s = ohneEmoji(s.replace(/\[\/?(?:honey|bloom|ask|err|muted|bold|dim|italic|b|i|u)\]/g, ''));
    if (p) s = s.replace(/\{(\w+)\}/g, (m, k) => (k in p ? p[k] : m));
    return s;
  }

  // ------------------------------------------------------------------ //
  //  Zustand
  // ------------------------------------------------------------------ //
  const S = {
    z: null,
    route: ['zuhause'],
    lauf: null,
    ereignisse: [],
    vorschau: null,
    ergebnis: null,
    rueck: { faelle: [], waben: [], index: 0 },
    wabenbau: null,
    reflexion: null,
    empfehlung: null,
    check: null,
    modi: null,
    ollama: null,
    e: null,
  };

  const einst = () => (S.z && S.z.einstellungen) || {};
  const projekt = () => (S.z && S.z.projekt && S.z.projekt.eingerichtet ? S.z.projekt : null);
  const animVoll = () => document.documentElement.dataset.anim === 'voll' &&
    !window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  function themaAktiv(pref) {
    if (pref === 'auto') {
      const h = new Date().getHours();
      return h >= 7 && h < 19 ? 'dark' : 'light';       // wie die Konsole: tags dunkel, abends hell
    }
    return pref === 'light' ? 'light' : 'dark';
  }

  function einstellungenAnwenden() {
    const e = einst();
    const root = document.documentElement;
    root.dataset.theme = themaAktiv(e.thema || 'dark');
    root.dataset.anim = e.animationen || 'voll';
    root.dataset.klartext = e.klartext ? '1' : '0';
    root.lang = (S.z && S.z.sprache) || 'de';
  }

  // ------------------------------------------------------------------ //
  //  Bausteine
  // ------------------------------------------------------------------ //
  function seitenKopf(bieneKey, klarKey, rechts) {
    const kl = einst().klartext;
    const oben = t(kl ? klarKey : bieneKey);
    const unten = t(kl ? bieneKey : klarKey);
    return `<div class="seiten-kopf"><div><h1 data-px="${esc(oben)}">${esc(oben)}</h1>` +
      `<p class="unterzeile">${esc(unten)}</p></div>${rechts || ''}</div>`;
  }

  /** Bienen-Begriff oder — im Klartext-Modus — die Klartext-Beschriftung. */
  const begriff = (b, k) => t(einst().klartext ? k : b);

  const px = (text, tag) => `<${tag || 'span'} data-px="${esc(text)}">${esc(text)}</${tag || 'span'}>`;

  function wabenbalken(anteil, n, vorher) {
    n = n || 18;
    const voll = Math.round(Math.max(0, Math.min(1, anteil || 0)) * n);
    const alt = vorher == null ? voll : Math.round(vorher * n);
    let h = '';
    for (let i = 0; i < n; i++) h += P.zelle(i < voll ? 1 : 0, i >= alt && i < voll ? 'neu' : '');
    return `<div class="wabenbalken" role="progressbar" aria-valuemin="0" aria-valuemax="100" ` +
      `aria-valuenow="${Math.round((anteil || 0) * 100)}">${h}</div>`;
  }

  const konfidenz = (k) => (k == null ? '' :
    `<span class="konfidenz">${P.zelle(k)}<span>${Math.round(k * 100)}&nbsp;%</span></span>`);

  function statusChip(status) {
    const m = {
      assigned: ['honig', 'web.st.assigned'], indexed: ['honig', 'web.st.indexed'],
      needs_review: ['frage', 'web.st.needs_review'], error: ['fehler', 'web.st.error'],
      dublette: ['bluete', 'web.st.dublette'], quarantined: ['aus', 'web.st.quarantined'],
      missing: ['aus', 'web.st.missing'], superseded: ['aus', 'web.st.superseded'],
      pending: ['bluete', 'web.st.pending'], plan: ['honig', 'web.st.plan'],
    }[status] || ['aus', status];
    return `<span class="chip ${m[0]}"><span class="punkt"></span>${esc(t(m[1]))}</span>`;
  }

  function groesse(b) {
    if (b < 1024) return `${b} B`;
    if (b < 1024 * 1024) return `${(b / 1024).toFixed(0)} KB`;
    return `${(b / 1024 / 1024).toFixed(1)} MB`;
  }

  function leer(spriteHtml, text, extra) {
    return `<div class="leer-zustand">${spriteHtml}<p>${esc(text)}</p>${extra || ''}</div>`;
  }

  function schlafendeBiene() {
    return `<span>${P.sprite('schlaf')}<span class="schlaf-z" aria-hidden="true">z</span></span>`;
  }

  function stileAnwenden(wurzel) {
    $$('[data-anteil]', wurzel).forEach((el) => el.style.setProperty('--anteil', el.dataset.anteil + '%'));
  }

  // ------------------------------------------------------------------ //
  //  Hinweise (Toasts), Funkeln, fliegende Bienen
  // ------------------------------------------------------------------ //
  function hinweis({ titel, text, art, icon, dauer }) {
    const el = document.createElement('div');
    el.className = `toast ${art || ''}`;
    el.setAttribute('role', art === 'fehler' ? 'alert' : 'status');
    el.innerHTML = `<span>${icon || P.sprite(art === 'fehler' ? 'frage' : 'topf')}</span>` +
      `<div><b>${esc(titel || '')}</b>${text ? `<span>${esc(text)}</span>` : ''}</div>` +
      `<button class="zu" type="button" aria-label="${esc(t('web.btn.close'))}">×</button>`;
    $('#hinweise').appendChild(el);
    const weg = () => el.remove();
    el.querySelector('.zu').addEventListener('click', weg);
    if (dauer !== 0) setTimeout(weg, dauer || (art === 'fehler' ? 9000 : 5500));
  }

  function fehler(e) {
    hinweis({ titel: t('web.toast.error'), text: e && e.message ? e.message : String(e), art: 'fehler' });
  }

  function mitte(el) {
    const r = el.getBoundingClientRect();
    return { x: r.left + r.width / 2, y: r.top + r.height / 2 };
  }

  function funkeln(el) {
    if (!animVoll() || !el) return;
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

  let letzterFlug = 0;
  function fliegen(vonEl, nachEl, { geist, links } = {}) {
    if (!animVoll() || !vonEl || !nachEl) return;
    const jetzt = performance.now();
    if (jetzt - letzterFlug < 140 || $$('.flieger').length > 10) return;
    letzterFlug = jetzt;
    const a = mitte(vonEl);
    const b = mitte(nachEl);
    const f = document.createElement('span');
    f.className = 'flieger' + (geist ? ' geist' : '');
    f.innerHTML = P.biene('flattert');
    $('#flugraum').appendChild(f);
    const s = links ? ' scaleX(-1)' : '';
    const hoch = Math.min(a.y, b.y) - 30 - Math.random() * 30;
    f.animate([
      { transform: `translate(${a.x - 14}px, ${a.y - 13}px)${s}` },
      { transform: `translate(${(a.x + b.x) / 2 - 14}px, ${hoch}px)${s}`, offset: 0.5 },
      { transform: `translate(${b.x - 14}px, ${b.y - 13}px)${s}` },
    ], { duration: 950, easing: 'steps(16, end)' }).finished.then(() => f.remove());
  }

  function feiern(erg, anker) {
    if (!erg) return;
    if (erg.sauber && !erg.vorschau) {
      hinweis({ titel: t('pl.celebrate'), text: t('web.toast.sorted', { n: erg.eingelagert }), art: 'erfolg' });
      funkeln(anker);
    }
    const sp = erg.spiel;
    if (!sp || !einst().fortschritt) return;
    for (const a of sp.neue_abzeichen || []) {
      hinweis({ titel: t('web.toast.badge', { name: a.name }), text: a.grund, art: 'erfolg', icon: plakette(a.key), dauer: 7000 });
    }
    if (sp.aufgestiegen) {
      hinweis({ titel: t('spiel.aufgestiegen', { stufe: sp.aufgestiegen }), text: t('web.toast.levelup'), art: 'erfolg', icon: P.sprite('krone'), dauer: 7000 });
      funkeln(anker);
    }
  }

  // ------------------------------------------------------------------ //
  //  Abzeichen — Plaketten aus den acht Abzeichen von spiel.py
  // ------------------------------------------------------------------ //
  const PLAKETTE = {
    erste_wabe: () => P.sprite('wabe'), zehn: () => px('10'), hundert: () => px('100'),
    lehrmeister: () => P.sprite('stift'), weise: () => P.sprite('krone'),
    blitzblank: () => P.sprite('funkeln'), serie: () => P.sprite('sonne'), vielfalt: () => P.sprite('blume'),
  };
  const plakette = (key) => `<span class="plakette"><span>${(PLAKETTE[key] || PLAKETTE.erste_wabe)()}</span></span>`;

  function stockKarte(st) {
    if (!st || !einst().fortschritt) return '';
    const weiter = st.schwelle
      ? `${st.dokumente}/${st.schwelle} · ${esc(t('spiel.bis_naechste', { n: st.fehlt }))}`
      : esc(t('spiel.maximum'));
    const abz = st.abzeichen.map((a) => `<div class="abzeichen ${a.verdient ? 'verdient' : ''}" ` +
      `title="${esc(a.grund)}">${plakette(a.key)}<b>${esc(a.name)}</b><small>${esc(a.grund)}</small>` +
      `<span class="sr-only">${esc(a.verdient ? t('web.stock.earned') : t('web.stock.open'))}</span></div>`).join('');
    return `<section class="karte stock" aria-labelledby="stock-titel">
      <div class="zeile weit"><h2 id="stock-titel">${esc(t('spiel.titel'))}</h2>
        <span class="leise klein">${esc(t('web.stock.only_real'))}</span></div>
      <div class="stock-kopf"><strong data-px="${esc(st.stufe_name)}">${esc(st.stufe_name)}</strong>
        <span class="leise">${esc(t('spiel.stufe'))} ${st.nummer}/${st.stufen}</span></div>
      ${wabenbalken(st.anteil)}
      <p class="leise klein">${weiter}</p>
      <p class="stock-zahlen">${esc(t('spiel.zahlen', { dokumente: st.dokumente, waben: st.waben, regeln: st.regeln, serie: st.serie }))}</p>
      <h3>${esc(t('spiel.abzeichen_titel', { n: st.abzeichen.filter((a) => a.verdient).length, gesamt: st.abzeichen.length }))}</h3>
      <div class="abzeichen-raster">${abz}</div>
    </section>`;
  }

  // ------------------------------------------------------------------ //
  //  Kopfzeile, Navigation, Statusleiste
  // ------------------------------------------------------------------ //
  const NAV = [
    [
      { id: 'zuhause', icon: 'haus', b: 'web.nav.home', k: 'web.nav.home.k' },
      { id: 'flugloch', icon: 'flugloch', b: 'web.nav.inbox', k: 'web.nav.inbox.k', zahl: (p) => p.lose },
      { id: 'rueckfragen', icon: 'frage', b: 'web.nav.review', k: 'web.nav.review.k', zahl: (p) => p.rueckfragen, frage: true },
      { id: 'waben', icon: 'wabe', b: 'web.nav.combs', k: 'web.nav.combs.k' },
    ],
    [
      { id: 'schwarm', icon: 'krone', b: 'web.nav.swarm', k: 'web.nav.swarm.k' },
      { id: 'wachstafel', icon: 'tafel', b: 'web.nav.rules', k: 'web.nav.rules.k' },
      { id: 'quarantaene', icon: 'kiste', b: 'web.nav.trash', k: 'web.nav.trash.k' },
      { id: 'werkstatt', icon: 'hammer', b: 'web.nav.workshop', k: 'web.nav.workshop.k' },
    ],
  ];

  function rahmenZeichnen() {
    const z = S.z;
    const p = projekt();
    $('#logo').innerHTML = P.biene() + `<span class="logo-wort" data-px="PollySort">PollySort</span>`;
    $('#sprung').textContent = t('web.skip');
    $('#projekt-wahl-label').textContent = t('web.project');

    const wahl = $('#projekt-wahl');
    wahl.innerHTML = (z.projekte || []).map((pr) => `<option value="${esc(pr.pfad)}" ${pr.aktiv ? 'selected' : ''}>` +
      `${esc(pr.name)}</option>`).join('') +
      (z.projekte && z.projekte.some((pr) => pr.aktiv) ? '' : `<option value="" selected>${esc(t('header.noproject'))}</option>`) +
      `<option value="__neu">${esc(t('web.project.new'))}</option>`;

    $('#modus-chip').innerHTML = p ? `<a class="chip" href="#/werkstatt" title="${esc(t('web.mode.title'))}">` +
      `${P.sprite('lupe')}${esc(p.modus_name)}</a>` : '';

    const w = z.wache || {};
    const wTxt = !p ? '' : w.aktiv
      ? (w.aktion === 'move' ? t('web.watch.move') : t('web.watch.notify')) : t('web.watch.off');
    $('#wache-chip').innerHTML = p ? `<button type="button" class="chip ${w.aktiv ? 'wache' : 'aus'}" data-tun="wache" ` +
      `aria-pressed="${w.aktiv ? 'true' : 'false'}" title="${esc(t(w.aktiv ? 'web.watch.pause' : 'web.watch.resume'))}">` +
      `${w.aktiv ? P.biene('wache-biene flattert') : '<span class="punkt"></span>'}${esc(wTxt)}</button>` : '';

    const rf = $('#rueckflug');
    rf.innerHTML = P.sprite('rueckflug') + `<span>${esc(t('web.undo'))}</span>`;
    rf.title = t('web.undo.title');
    rf.hidden = !p;
    rf.disabled = !(p && p.kann_rueckflug);

    $('#leiste').setAttribute('aria-label', t('web.nav'));
    $('#leiste').innerHTML = NAV.map((gruppe) => `<div class="leiste-gruppe">` + gruppe.map((n) => {
      const zahl = p && n.zahl ? n.zahl(p) : 0;
      const aktuell = S.route[0] === n.id || (S.route[0] === 'einrichten' && n.id === 'werkstatt');
      return `<a class="nav-punkt" href="#/${n.id}" ${aktuell ? 'aria-current="page"' : ''}>` +
        `${P.sprite(n.icon)}<span class="begriffe"><span class="biene-wort">${esc(t(n.b))}</span>` +
        `<span class="klar">${esc(t(n.k))}</span></span>` +
        (zahl ? `<span class="zaehler ${n.frage ? 'frage' : ''}" aria-label="${esc(t('web.count', { n: zahl }))}">${zahl}</span>` : '<span></span>') +
        `</a>`;
    }).join('') + `</div>`).join('');

    $('#polly-biene').innerHTML = P.biene(S.lauf ? 'flattert' : '');
    $('#protokoll-knopf').textContent = t('web.log');
    $('#protokoll-titel').textContent = t('web.log.title');
    $('#protokoll-zu').textContent = t('web.btn.close');
    if (!$('#polly').textContent) $('#polly').textContent = t('web.polly.hello');
    P.schrift($('.kopf'));
    kopfMessen();
    // Schmale Bildschirme: Die Leiste rollt waagerecht — den aktiven Punkt sichtbar halten.
    const aktiv = $('.nav-punkt[aria-current="page"]');
    if (aktiv && window.matchMedia('(max-width: 860px)').matches) {
      const leiste = $('#leiste');
      leiste.scrollLeft = aktiv.offsetLeft - (leiste.clientWidth - aktiv.offsetWidth) / 2;
    }
  }

  function kopfMessen() {
    document.documentElement.style.setProperty('--kopf-hoehe', `${$('.kopf').offsetHeight}px`);
  }

  function pollySagt(e) {
    const el = $('#polly');
    el.innerHTML = `<span class="art-${esc(e.art)}">${symbol(e.emoji, e.art)} ${esc(ohneEmoji(e.text))}</span>`;
  }

  function protokollZeichnen() {
    const liste = $('#protokoll-liste');
    if ($('#protokoll').hidden) return;
    liste.innerHTML = S.ereignisse.slice().reverse().map((e) =>
      `<li class="art-${esc(e.art)}"><time>${esc(e.zeit || '')}</time><span>${symbol(e.emoji, e.art)}</span>` +
      `<span>${esc(ohneEmoji(e.text))}</span></li>`).join('') || `<li><span></span><span></span><span class="leise">${esc(t('web.log.empty'))}</span></li>`;
  }

  // ------------------------------------------------------------------ //
  //  Ereignisstrom (Server-Sent Events, gelesen per fetch — mit Token im Header)
  // ------------------------------------------------------------------ //
  let auffrischenGeplant = null;
  function spaeterAuffrischen(ms) {
    clearTimeout(auffrischenGeplant);
    auffrischenGeplant = setTimeout(() => zustandLaden().then(() => { rahmenZeichnen(); if (!S.lauf) seiteZeichnen(true); }), ms || 300);
  }

  function ereignis(e) {
    if (['honey', 'bloom', 'ask', 'error', 'info', 'raw', 'rule', 'feier'].includes(e.art)) {
      S.ereignisse.push(e);
      if (S.ereignisse.length > 300) S.ereignisse.shift();
      if (e.art !== 'raw' && e.art !== 'rule') pollySagt(e);
      protokollZeichnen();
      return;
    }
    if (e.art === 'fortschritt' && S.lauf) {
      const vorher = S.lauf.gesamt ? S.lauf.erledigt / S.lauf.gesamt : 0;
      S.lauf.erledigt = e.erledigt;
      S.lauf.gesamt = e.gesamt;
      S.lauf.text = e.text;
      S.lauf.einheit = e.einheit || null;
      laufZeichnen(vorher);
      if (e.erledigt > 0 && !e.einheit) fliegen($('#station-eingang'), $('#station-waben'), { geist: S.lauf.name === 'vorschau' });
      return;
    }
    if (e.art === 'wache') {
      if (S.z) { S.z.wache = { aktiv: e.aktiv, aktion: e.aktion, echtzeit: e.echtzeit }; rahmenZeichnen(); }
      return;
    }
    if (e.art === 'wache_lauf') {
      const erg = e.ergebnis || {};
      if (erg.eingelagert) hinweis({ titel: t('web.toast.watch_sorted', { n: erg.eingelagert }), art: 'erfolg' });
      feiern({ ...erg, sauber: false });
      spaeterAuffrischen(200);
      return;
    }
    if (e.art === 'eingang') {
      hinweis({ titel: t('web.toast.new_files', { n: e.neu }), text: t('web.toast.new_files.text'), icon: P.sprite('flugloch') });
      spaeterAuffrischen(200);
      return;
    }
    // Das automatische Update startet der Server selbst (beim Start der App) — die Seite zeigt es
    // wie eine eigene lange Aktion an und sagt am Ende, ob die Modelle jetzt passen.
    if (e.art === 'auftrag' && e.name === 'modelle_aktualisieren') {
      if (e.zustand === 'start') {
        hintergrundZeigen();
      } else if (S.lauf && S.lauf.hintergrund) {
        S.lauf = null;
        zustandLaden().then(() => {
          const bn = S.z.beenara || {};
          const ok = e.zustand === 'ende' && (!bn.vorhanden || bn.passend);
          hinweis(ok ? { titel: t('web.toast.update.done'), text: t('web.toast.update.done.text'), art: 'erfolg' }
            : { titel: t('web.toast.update.failed'), text: t('web.toast.bn.failed.text'), art: 'fehler' });
          rahmenZeichnen(); seiteZeichnen(true);
        });
      }
      return;
    }
    if (e.art === 'auftrag' && e.zustand !== 'start' && !S.lauf) spaeterAuffrischen(400);
  }

  // Läuft das automatische Update schon, wenn die Seite (neu) lädt, hat sie den Start verpasst.
  function hintergrundZeigen() {
    if (S.lauf) return;
    S.lauf = { name: 'modelle_aktualisieren', erledigt: 0, gesamt: 0, text: '', hintergrund: true };
    rahmenZeichnen();
    laufZeichnen();
  }

  async function stromVerbinden() {
    for (;;) {
      try {
        const antwort = await fetch('/api/ereignisse', { headers: { 'X-Flugbrett-Token': TOKEN } });
        if (!antwort.ok || !antwort.body) throw new Error('strom');
        const leser = antwort.body.getReader();
        const dec = new TextDecoder();
        let puffer = '';
        for (;;) {
          const { value, done } = await leser.read();
          if (done) break;
          puffer += dec.decode(value, { stream: true });
          let i;
          while ((i = puffer.indexOf('\n\n')) >= 0) {
            const block = puffer.slice(0, i);
            puffer = puffer.slice(i + 2);
            for (const zeile of block.split('\n')) {
              if (zeile.startsWith('data: ')) {
                try { ereignis(JSON.parse(zeile.slice(6))); } catch (err) { /* kaputte Zeile */ }
              }
            }
          }
        }
      } catch (err) { /* neu verbinden */ }
      await new Promise((r) => setTimeout(r, 2500));
    }
  }

  // ------------------------------------------------------------------ //
  //  Arbeit: lange Aktionen mit Fortschritt
  // ------------------------------------------------------------------ //
  // Während eine lange Aktion läuft, sind die Knöpfe ihrer Karte gesperrt — sonst startet ein
  // zweiter Klick dieselbe Aktion noch einmal (z. B. „Herunterladen" während des Downloads).
  function karteSperren() {
    const lauf = $('#lauf');
    const karte = lauf && lauf.closest('section');
    if (!karte) return () => {};
    const knoepfe = $$('button, input, select', karte).filter((k) => !k.disabled);
    knoepfe.forEach((k) => { k.disabled = true; });
    karte.setAttribute('aria-busy', 'true');
    return () => {
      knoepfe.forEach((k) => { k.disabled = false; });
      karte.removeAttribute('aria-busy');
    };
  }

  async function arbeit(name, daten) {
    if (S.lauf) { hinweis({ titel: t('web.err.busy'), art: 'fehler' }); return null; }
    S.lauf = { name, erledigt: 0, gesamt: 0, text: '' };
    rahmenZeichnen();
    laufZeichnen();
    const freigeben = karteSperren();
    try {
      return await tun(name, daten);
    } catch (e) {
      fehler(e);
      return null;
    } finally {
      freigeben();
      S.lauf = null;
      await zustandLaden();
      rahmenZeichnen();
    }
  }

  // Der Fortschritt einer langen Aktion — im Flugloch, in der Werkstatt und im Assistenten.
  function laufBlock() {
    return `<div id="lauf" hidden class="stapel">
            <div class="zeile weit"><b id="lauf-titel"></b><span id="lauf-zahl" class="mono"></span></div>
            <div id="lauf-balken"></div>
            <div id="lauf-text" class="fortschritt-text"></div>
          </div>`;
  }

  const mb = (bytes) => Math.round(bytes / 1e6);

  function laufZeichnen(vorher) {
    const ort = $('#lauf');
    if (!ort) return;
    if (!S.lauf) { ort.hidden = true; return; }
    ort.hidden = false;
    const anteil = S.lauf.gesamt ? S.lauf.erledigt / S.lauf.gesamt : 0;
    $('#lauf-balken').innerHTML = wabenbalken(anteil, 18, vorher);
    $('#lauf-zahl').textContent = !S.lauf.gesamt ? ''
      : S.lauf.einheit === 'bytes' ? `${mb(S.lauf.erledigt)}/${mb(S.lauf.gesamt)} MB` : `${S.lauf.erledigt}/${S.lauf.gesamt}`;
    if (S.lauf.name === 'beenara_laden' || S.lauf.name === 'beenara_big_laden') {
      const big = S.lauf.name === 'beenara_big_laden';
      $('#lauf-titel').textContent = t(big ? 'web.run.bb.title' : 'web.run.beenara.title');
      $('#lauf-text').textContent = S.lauf.text || (big ? '' : t('bn.checking', { repo: (S.z.beenara || {}).repo || '' }));
      return;
    }
    if (S.lauf.name === 'modelle_aktualisieren') {
      $('#lauf-titel').textContent = t('web.run.update.title');
      $('#lauf-text').textContent = S.lauf.text || '';
      return;
    }
    if (S.lauf.name === 'ollama_modell_laden') {
      $('#lauf-titel').textContent = t('web.run.om.title');
      $('#lauf-text').textContent = S.lauf.text || t('om.checking', { modell: ollamaZiel });
      return;
    }
    $('#lauf-text').textContent = S.lauf.text || t(S.lauf.name === 'vorschau' ? 'web.run.preview' : 'web.run.sort');
    $('#lauf-titel').textContent = t(S.lauf.name === 'vorschau' ? 'web.run.preview.title' : 'web.run.sort.title');
  }

  // ------------------------------------------------------------------ //
  //  Seiten
  // ------------------------------------------------------------------ //
  function ohneProjekt() {
    return `${seitenKopf('web.nav.home', 'web.nav.home.k')}
      <section class="karte leer-zustand">${P.biene('flattert')}
        <h2 data-px="${esc(t('web.welcome'))}">${esc(t('web.welcome'))}</h2>
        <p>${esc(t('firstrun.what'))}</p>
        <p><a class="knopf gross" href="#/einrichten">${P.sprite('flugloch')}${esc(t('web.setup.start'))}</a></p>
      </section>`;
  }

  // -- Zuhause ----------------------------------------------------------------
  function seiteZuhause() {
    const p = projekt();
    if (!p) return ohneProjekt();
    const kacheln = [];
    kacheln.push(`<section class="karte kachel">
      <div class="kachel-kopf">${P.sprite('flugloch')}<h2>${esc(t('web.home.inbox'))}</h2></div>
      ${p.lose ? `<div class="zahl">${px(p.lose)}</div><p class="zahl-text">${esc(t('web.home.inbox.some', { n: p.lose }))}</p>`
        : `<div>${schlafendeBiene()}</div><p class="zahl-text">${esc(t('inbox.empty'))}</p>`}
      <div class="aktionen">
        <button class="knopf" type="button" data-tun="vorschau-start" ${p.lose ? '' : 'disabled'}>${esc(t('web.btn.preview'))}</button>
        <button class="knopf zweit" type="button" data-tun="sortieren-start" ${p.lose ? '' : 'disabled'}>${esc(t('web.btn.sort'))}</button>
      </div></section>`);
    kacheln.push(`<section class="karte kachel ${p.rueckfragen ? 'frage' : ''}">
      <div class="kachel-kopf">${P.sprite('frage')}<h2>${esc(begriff('web.nav.review', 'web.nav.review.k'))}</h2></div>
      <div class="zahl">${px(p.rueckfragen)}</div>
      <p class="zahl-text">${esc(t(p.rueckfragen ? 'web.home.review.some' : 'rv.none'))}</p>
      <div class="aktionen"><a class="knopf ${p.rueckfragen ? '' : 'zweit'}" href="#/rueckfragen" ${p.rueckfragen ? '' : 'aria-disabled="true"'}>${esc(t('web.btn.answer'))}</a></div>
    </section>`);
    kacheln.push(`<section class="karte kachel">
      <div class="kachel-kopf">${P.sprite('wabe')}<h2>${esc(begriff('web.nav.combs', 'web.nav.combs.k'))}</h2></div>
      <div class="zahl">${px(p.sortiert)}</div>
      <p class="zahl-text">${esc(t('web.home.sorted', { n: p.waben }))}</p>
      <div class="aktionen"><a class="knopf zweit" href="#/waben">${esc(t('web.btn.combs'))}</a></div>
    </section>`);
    if (p.fehler) {
      kacheln.push(`<section class="karte kachel fehler">
        <div class="kachel-kopf">${P.sprite('warnung')}<h2>${esc(t('web.st.error'))}</h2></div>
        <div class="zahl">${px(p.fehler)}</div><p class="zahl-text">${esc(t('web.home.errors'))}</p>
        <div class="aktionen"><a class="knopf zweit" href="#/waben/_fehler">${esc(t('web.btn.show'))}</a></div></section>`);
    }
    if (p.deadlines) {
      kacheln.push(`<section class="karte kachel frage">
        <div class="kachel-kopf"><span class="${animVoll() ? 'wackeln' : ''}">${P.sprite('glocke')}</span><h2>${esc(t('r.cal.title'))}</h2></div>
        <div class="zahl">${px(p.deadlines)}</div><p class="zahl-text">${esc(t('web.home.deadlines'))}</p>
        <div class="aktionen"><a class="knopf zweit" href="#/schwarm">${esc(t('web.btn.calendar'))}</a></div></section>`);
    }
    const projekte = (S.z.projekte || []).length > 1 ? `<section class="karte"><h2>${esc(t('projects.title'))}</h2>
      <table class="liste"><tbody>${S.z.projekte.map((pr) => `<tr><td><b>${esc(pr.name)}</b><div class="pfad">${esc(pr.pfad)}</div></td>
      <td>${pr.aktiv ? `<span class="chip honig">${esc(t('web.active'))}</span>` :
        `<button class="knopf zweit klein-knopf" type="button" data-tun="wechseln" data-pfad="${esc(pr.pfad)}">${esc(t('web.btn.open'))}</button>`}</td></tr>`).join('')}
      </tbody></table></section>` : '';
    return `${seitenKopf('web.nav.home', 'web.nav.home.k')}
      <div class="stapel">
        <section class="karte projekt-karte">
          ${p.lose ? P.biene('flattert') : P.sprite('schlaf')}
          <div><h2 data-px="${esc(p.name)}">${esc(p.name)}</h2><div class="pfad">${esc(p.pfad)}</div>
          <div class="zeile klein">${esc(t('home.mode', { provider: p.modus_name, watch: t('web.watchmode.' + p.wache) }))}</div></div>
        </section>
        <div class="raster">${kacheln.join('')}</div>
        ${stockKarte(S.z.stock)}
        ${projekte}
      </div>`;
  }

  // -- Flugloch (Eingang & Sortieren) -------------------------------------------
  async function seiteFlugloch() {
    const p = projekt();
    if (!p) return ohneProjekt();
    const eingang = await lesen('eingang');
    const dateien = eingang.dateien || [];
    let vorschau = '';
    if (S.vorschau) {
      const v = S.vorschau;
      const zeilen = v.plan.map((z) => `<tr><td class="datei">${esc(z.datei)}</td>
        <td>${z.status === 'assigned' ? `<b>${esc(z.wabe.name)}</b>${z.ziel ? `<div class="pfad">${esc(z.ziel)}</div>` : ''}` : '<span class="leise">—</span>'}</td>
        <td>${konfidenz(z.konfidenz)}${z.quelle_text ? `<div class="leise klein">${esc(z.quelle_text)}</div>` : ''}</td><td>${statusChip(z.status === 'assigned' ? 'plan' : z.status)}</td></tr>`).join('');
      vorschau = `<section class="karte" id="vorschau-karte" aria-labelledby="vorschau-titel">
        <div class="zeile weit"><h2 id="vorschau-titel">${esc(t('web.preview.title'))}</h2><span class="chip bluete">${esc(t('pl.rule.preview'))}</span></div>
        <div class="plan-summe">
          <span class="chip honig">${esc(t('web.preview.would', { n: v.eingelagert }))}</span>
          ${v.rueckfragen ? `<span class="chip frage">${esc(t('web.preview.review', { n: v.rueckfragen }))}</span>` : ''}
          ${v.dubletten ? `<span class="chip bluete">${esc(t('web.preview.dups', { n: v.dubletten }))}</span>` : ''}
          ${v.fehler ? `<span class="chip fehler">${esc(t('web.preview.errors', { n: v.fehler }))}</span>` : ''}
        </div>
        ${zeilen ? `<div class="tabelle-huelle"><table class="liste"><thead><tr><th>${esc(t('r.col.file'))}</th><th>${esc(t('web.col.target'))}</th>
          <th>${esc(t('web.col.confidence'))}</th><th>${esc(t('web.col.status'))}</th></tr></thead><tbody>${zeilen}</tbody></table></div>` : ''}
        <p class="hinweis">${esc(t('pl.preview_note'))} ${esc(t('web.preview.cache'))}</p>
        <div class="zeile">
          <button class="knopf gross" type="button" data-tun="anwenden" ${v.eingelagert ? '' : 'disabled'}>${P.sprite('topf')}${esc(t('web.btn.apply'))}</button>
          <button class="knopf zweit" type="button" data-tun="verwerfen">${esc(t('web.btn.discard'))}</button>
        </div></section>`;
    }
    let ergebnis = '';
    if (S.ergebnis) {
      const e = S.ergebnis;
      const max = Math.max(1, ...e.waben.map((w) => w.anzahl));
      const ki = e.ki_anfragen ? (e.modus === 'openrouter'
        ? t('pl.calls_online', { n: e.ki_anfragen, cost: (e.kosten || 0).toFixed(4) })
        : e.modus === 'ollama' ? t('pl.calls_local', { n: e.ki_anfragen }) : t('pl.calls_offline', { n: e.ki_anfragen })) : '';
      ergebnis = `<section class="karte" id="ergebnis-karte" aria-labelledby="ergebnis-titel">
        <div class="zeile weit"><h2 id="ergebnis-titel">${esc(t('web.result.title'))}</h2>
          ${e.sauber ? `<span class="chip honig">${P.sprite('topf')}${esc(t('pl.celebrate'))}</span>` : ''}</div>
        ${e.waben.length ? `<div class="balken-liste">${e.waben.map((w) => `<div class="balken-zeile"><b>${esc(w.name)}</b>
          <span class="balken"><span data-anteil="${Math.round((w.anzahl / max) * 100)}"></span></span><span>${w.anzahl}</span></div>`).join('')}</div>`
        : `<p class="leise">${esc(t('web.result.none'))}</p>`}
        <div class="plan-summe">
          ${e.rueckfragen ? `<a class="chip frage" href="#/rueckfragen">${esc(t('web.preview.review', { n: e.rueckfragen }))}</a>` : ''}
          ${e.dubletten ? `<a class="chip bluete" href="#/quarantaene">${esc(t('web.preview.dups', { n: e.dubletten }))}</a>` : ''}
          ${e.fehler ? `<a class="chip fehler" href="#/waben/_fehler">${esc(t('web.preview.errors', { n: e.fehler }))}</a>` : ''}
        </div>
        ${e.quellen_text ? `<p class="hinweis">${esc(e.quellen_text)}</p>` : ''}
        ${ki ? `<p class="hinweis">${esc(ki)}</p>` : ''}
      </section>`;
    }
    const liste = dateien.length
      ? `<div class="tabelle-huelle"><table class="liste"><thead><tr><th>${esc(t('r.col.file'))}</th><th>${esc(t('web.col.size'))}</th><th>${esc(t('web.col.changed'))}</th></tr></thead>
        <tbody>${dateien.map((d) => `<tr><td class="datei">${esc(d.datei)}</td><td>${groesse(d.groesse)}</td><td class="leise">${esc(d.geaendert)}</td></tr>`).join('')}</tbody></table></div>`
      : leer(schlafendeBiene(), t('inbox.empty'));
    return `${seitenKopf('web.nav.inbox', 'web.nav.inbox.k')}
      <div class="stapel">
        <section class="karte" aria-labelledby="flug-titel">
          <h2 id="flug-titel" class="sr-only">${esc(t('web.nav.inbox'))}</h2>
          <div class="flugbahn">
            <div class="station" id="station-eingang">${P.sprite('flugloch')}<b>${px(dateien.length)}</b><span>${esc(t('web.inbox.loose'))}</span></div>
            <div class="bahn"></div>
            <div class="station" id="station-waben">${P.sprite('wabe')}<b>${px(p.waben)}</b><span>${esc(t('web.nav.combs'))}</span></div>
          </div>
          ${laufBlock()}
          <div class="zeile" id="flug-aktionen">
            <button class="knopf gross" type="button" data-tun="vorschau" ${dateien.length ? '' : 'disabled'}>${P.sprite('lupe')}${esc(t('web.btn.preview'))} <span class="tastenkuerzel">v</span></button>
            <button class="knopf zweit gross" type="button" data-tun="sortieren" ${dateien.length ? '' : 'disabled'}>${P.sprite('topf')}${esc(t('web.btn.sort'))} <span class="tastenkuerzel">s</span></button>
            <label class="zeile klein"><input type="checkbox" id="turbo"> ${esc(t('web.turbo'))}</label>
          </div>
          <p class="hinweis">${esc(t('web.inbox.explain'))}</p>
        </section>
        ${vorschau}${ergebnis}
        <section class="karte"><h2>${esc(t('web.inbox.files'))}</h2>${liste}</section>
        <details class="karte"><summary><b>${esc(t('web.tools'))}</b></summary>
          <div class="raster-2 abstand">
            <div><h3>${esc(t('web.import.title'))}</h3>
              <label class="feld"><span>${esc(t('web.import.label'))}</span><input type="text" id="import-ordner" placeholder="C:\\Users\\…\\Downloads"></label>
              <p class="hinweis">${esc(t('help.d.import'))}</p>
              <button class="knopf zweit" type="button" data-tun="importieren">${esc(t('web.btn.import'))}</button></div>
            <div><h3>${esc(t('web.scan.title'))}</h3><p class="hinweis">${esc(t('help.d.scan'))}</p>
              <button class="knopf zweit" type="button" data-tun="scan">${P.sprite('lupe')}${esc(t('web.btn.scan'))}</button></div>
          </div>
        </details>
      </div>`;
  }

  // -- Rückfragen ---------------------------------------------------------------
  async function seiteRueckfragen() {
    if (!projekt()) return ohneProjekt();
    const daten = await lesen('rueckfragen');
    S.rueck = { faelle: daten.faelle, waben: daten.waben, index: Math.min(S.rueck.index, Math.max(0, daten.faelle.length - 1)) };
    return seitenKopf('web.nav.review', 'web.nav.review.k') + rueckKarte();
  }

  function rueckKarte() {
    const { faelle, waben, index } = S.rueck;
    if (!faelle.length) return `<section class="karte">${leer(P.sprite('topf'), t('rv.none'), `<p><a class="knopf zweit" href="#/zuhause">${esc(t('web.btn.home'))}</a></p>`)}</section>`;
    const f = faelle[index];
    const zellen = faelle.map((_, i) => P.zelle(i < index ? 1 : i === index ? 0.5 : 0)).join('');
    const vorschlagOk = f.vorschlag && f.vorschlag.key !== '_unassigned';
    const chips = waben.map((w, i) => `<button type="button" class="chip ${vorschlagOk && w.key === f.vorschlag.key ? 'honig' : ''}" data-tun="rueck-wahl" data-kat="${esc(w.key)}">` +
      `${i < 9 ? `<kbd>${i + 1}</kbd>` : ''}${esc(w.name)}</button>`).join('');
    return `<div class="rueck">
      <div class="rueck-zaehler" aria-hidden="true">${zellen}</div>
      <p class="leise">${esc(t('web.review.case', { i: index + 1, n: faelle.length }))}</p>
      <section class="karte rueck-karte" aria-labelledby="rueck-datei">
        <h2 id="rueck-datei">${esc(f.datei)}</h2>
        <dl>
          <dt>${esc(t('web.review.title'))}</dt><dd>${esc(f.titel || '—')}</dd>
          <dt>${esc(t('web.review.function'))}</dt><dd>${esc(f.funktion || '—')}</dd>
          <dt>${esc(t('web.review.suggestion'))}</dt><dd>${vorschlagOk ? `<b>${esc(f.vorschlag.name)}</b> ${konfidenz(f.konfidenz)}` : `<span class="leise">${esc(t('web.review.nosuggestion'))}</span>`}</dd>
          ${f.zusammenfassung ? `<dt>${esc(t('web.review.summary'))}</dt><dd class="klein">${esc(f.zusammenfassung)}</dd>` : ''}
        </dl>
        <h3>${esc(t('web.review.which'))}</h3>
        <div class="waben-wahl">${chips}</div>
        <form class="zeile" data-form="rueck-neu">
          <label class="sr-only" for="rueck-neu">${esc(t('web.review.newcomb'))}</label>
          <input type="text" id="rueck-neu" placeholder="${esc(t('web.review.newcomb'))}" class="breite-s">
          <button class="knopf zweit klein-knopf" type="submit">${esc(t('web.btn.newcomb'))}</button>
        </form>
        <div class="zeile abstand">
          <button class="knopf" type="button" data-tun="rueck-ok" ${vorschlagOk ? '' : 'disabled'}>${esc(t('web.btn.accept'))} <span class="tastenkuerzel">⏎</span></button>
          <button class="knopf zweit" type="button" data-tun="rueck-skip">${esc(t('web.btn.skip'))} <span class="tastenkuerzel">s</span></button>
          <button class="knopf leise-knopf" type="button" data-tun="rueck-oeffnen" ${f.vorhanden ? '' : 'disabled'}>${P.sprite('auge')}${esc(t('web.btn.view'))} <span class="tastenkuerzel">v</span></button>
        </div>
        <p class="hinweis"><span id="lernt" class="lernt" aria-live="polite"></span> ${esc(t('web.review.learns'))}</p>
      </section></div>`;
  }

  // -- Waben ------------------------------------------------------------------
  async function seiteWaben() {
    if (!projekt()) return ohneProjekt();
    const daten = await lesen('waben');
    const auswahl = S.route[1] ? decodeURIComponent(S.route[1]) : '';
    const suche = auswahl === '_suche' ? decodeURIComponent(S.route[2] || '') : '';
    const max = Math.max(1, ...daten.waben.map((w) => w.anzahl));
    const kacheln = daten.waben.map((w) => `<a class="wabe-kachel" href="#/waben/${encodeURIComponent(w.key)}" data-wabe="${esc(w.key)}" ${auswahl === w.key ? 'aria-current="true"' : ''}>
        ${P.zelle(w.anzahl / max)}<span class="name">${esc(w.name)}</span><span class="anzahl">${px(w.anzahl)}</span>
        <span class="marken">${w.unterordner ? `<span class="chip">${esc(w.unterordner)}</span>` : ''}${w.projekt ? `<span class="chip honig">${esc(t('web.combs.project'))}</span>` : ''}</span></a>`).join('');
    let eintraege = '';
    if (auswahl) {
      const params = auswahl === '_fehler' ? { status: 'error' } : auswahl === '_suche' ? { suche } : { kategorie: auswahl };
      const e = await lesen('eintraege', params);
      const w = daten.waben.find((x) => x.key === auswahl);
      const titel = auswahl === '_fehler' ? t('web.st.error') : auswahl === '_suche' ? t('web.combs.search_hits', { q: suche }) : (w ? w.name : auswahl);
      const optionen = daten.waben.map((x) => `<option value="${esc(x.key)}">${esc(x.name)}</option>`).join('');
      const zeilen = e.eintraege.map((r) => `<tr draggable="true" data-id="${esc(r.id)}">
        <td><b>${esc(r.titel || r.datei)}</b><div class="datei leise">${esc(r.datei)}</div>${r.stichworte.length ? `<div class="klein leise">${esc(r.stichworte.join(' · '))}</div>` : ''}</td>
        <td>${statusChip(r.status)}${auswahl.startsWith('_') ? `<div class="klein">${esc(r.wabe.name)}</div>` : ''}</td>
        <td class="leise klein">${esc(r.datum)}</td>
        <td><div class="zeile">
          <label class="sr-only" for="um-${esc(r.id)}">${esc(t('web.combs.move'))}</label>
          <select id="um-${esc(r.id)}" data-umsortieren="${esc(r.id)}"><option value="">${esc(t('web.combs.move'))}</option>${optionen}</select>
          <button class="knopf leise-knopf klein-knopf" type="button" data-tun="analysieren" data-id="${esc(r.id)}" title="${esc(t('help.d.reanalyze'))}">${P.sprite('lupe')}<span class="sr-only">${esc(t('web.btn.reanalyze'))}</span></button>
          <button class="knopf leise-knopf klein-knopf" type="button" data-tun="oeffnen" data-id="${esc(r.id)}" ${r.vorhanden ? '' : 'disabled'} title="${esc(t('web.btn.view'))}">${P.sprite('auge')}<span class="sr-only">${esc(t('web.btn.view'))}</span></button>
          <button class="knopf leise-knopf klein-knopf" type="button" data-tun="papierkorb" data-id="${esc(r.id)}" title="${esc(t('web.btn.quarantine'))}">${P.sprite('kiste')}<span class="sr-only">${esc(t('web.btn.quarantine'))}</span></button>
        </div></td></tr>`).join('');
      const wabenSetup = w ? `<div class="raster-2 abstand">
          <form class="karte" data-form="unterordner" data-kat="${esc(w.key)}"><h3>${esc(t('r.sub.title'))}</h3>
            <label class="feld"><span>${esc(t('web.combs.pattern'))}</span><input type="text" name="muster" value="${esc(w.unterordner || '')}" placeholder="${esc(daten.muster)}"></label>
            <p class="hinweis">${esc(t('help.d.subfolder', { pattern: daten.muster }))}</p>
            <div class="zeile"><button class="knopf zweit" type="submit">${esc(t('web.btn.save'))}</button>
            ${w.unterordner ? `<button class="knopf leise-knopf" type="button" data-tun="unterordner-aus" data-kat="${esc(w.key)}">${esc(t('web.btn.remove'))}</button>` : ''}</div>
          </form>
          <form class="karte" data-form="wabenbau" data-kat="${esc(w.key)}"><h3>${P.sprite('hammer')} ${esc(t('web.charter.title'))}</h3>
            <p class="hinweis">${esc(t('help.d.charter'))}</p>
            <label class="feld"><span>${esc(t('web.charter.who'))}</span><input type="text" name="wer" value="${esc((w.personen || []).join(', '))}"></label>
            <label class="feld"><span>${esc(t('web.charter.goal'))}</span><input type="text" name="ziel"></label>
            <label class="feld"><span>${esc(t('web.charter.deadline'))}</span><input type="date" name="deadline"></label>
            <div class="zeile abstand"><button class="knopf zweit" type="submit">${esc(t('web.btn.charter'))}</button></div>
            ${S.wabenbau && S.wabenbau.wabe.key === w.key ? `<div class="hinweis">${esc(t('r.charter.built', { path: S.wabenbau.datei }))}
              ${S.wabenbau.aufgaben.length ? `<ul>${S.wabenbau.aufgaben.map((a) => `<li>${esc(a)}</li>`).join('')}</ul>` : `<p>${esc(t('r.charter.done'))}</p>`}</div>` : ''}
          </form></div>` : '';
      eintraege = `<section class="karte" aria-labelledby="eintraege-titel">
        <div class="zeile weit"><h2 id="eintraege-titel">${esc(titel)}</h2><span class="leise">${esc(t('web.combs.count', { n: e.gesamt }))}</span></div>
        ${zeilen ? `<p class="hinweis">${esc(t('web.combs.drag'))}</p><div class="tabelle-huelle"><table class="liste"><thead><tr><th>${esc(t('r.col.title'))}</th><th>${esc(t('web.col.status'))}</th><th>${esc(t('web.col.date'))}</th><th>${esc(t('web.col.actions'))}</th></tr></thead><tbody>${zeilen}</tbody></table></div>`
          : leer(P.sprite('wabe'), t('r.nohits'))}
        ${wabenSetup}
      </section>`;
    }
    const sucheForm = `<form class="zeile" data-form="suche" role="search"><label class="sr-only" for="suche">${esc(t('web.combs.search'))}</label>
      <input type="search" id="suche" value="${esc(suche)}" placeholder="${esc(t('web.combs.search'))}" class="breite-m">
      <button class="knopf zweit" type="submit">${P.sprite('lupe')}<span class="sr-only">${esc(t('web.combs.search'))}</span></button></form>`;
    return `${seitenKopf('web.nav.combs', 'web.nav.combs.k', sucheForm)}
      <div class="stapel">
        <section class="karte"><div class="zeile weit"><h2>${esc(t('web.combs.all', { n: daten.waben.length }))}</h2><span class="leise">${esc(t('web.combs.total', { n: daten.gesamt }))}</span></div>
          <div class="waben-raster">${kacheln}</div></section>
        ${eintraege}
      </div>`;
  }

  // -- Schwarm ----------------------------------------------------------------
  async function seiteSchwarm() {
    if (!projekt()) return ohneProjekt();
    const s = await lesen('schwarm');
    const rolle = (sprite, titelKey, zahl, text, extra) => `<section class="karte rolle">${sprite}<div>
      <h2>${esc(t(titelKey))}</h2><div class="zahl-gross">${zahl}</div><p class="leise">${esc(text)}</p>${extra || ''}</div></section>`;
    const termine = s.termine.length ? s.termine.map((x) => `<div class="termin">
        <span class="marke ${x.tage < 0 ? 'rot' : x.tage <= 7 ? 'orange' : 'gruen'}" aria-hidden="true"></span>
        <div><b>${esc(x.titel)}</b><div class="leise klein mono">${esc(x.faellig)}</div></div>
        <span class="chip ${x.tage < 0 ? 'fehler' : x.tage <= 7 ? 'frage' : 'wache'}">${esc(x.tage >= 0 ? t('r.cal.in', { n: x.tage }) : t('r.cal.overdue', { n: -x.tage }))}</span></div>`).join('')
      : leer(P.sprite('kalender'), t('r.cal.empty'));
    const gew = s.gewohnheiten.length ? `<ul class="klein">${s.gewohnheiten.map((g) => `<li><b>${esc(g.wabe.name)}</b> → <span class="mono">${esc(g.ort)}</span></li>`).join('')}</ul>` : '';
    const emp = S.empfehlung ? `<ul>${S.empfehlung.hinweise.map((h) => `<li>${esc(h.replace(/^▸\s*/, ''))}</li>`).join('')}</ul>` : '';
    return `${seitenKopf('web.nav.swarm', 'web.nav.swarm.k')}
      <div class="stapel">
        <div class="raster-2">
          ${rolle(P.sprite('krone'), 'web.role.queen', px(s.waben), t('web.role.queen.text', { waben: s.waben, docs: s.dokumente }))}
          ${rolle(P.biene(), 'web.role.scouts', px(s.assigned), t('web.role.scouts.text', { review: s.needs_review, errors: s.error }))}
          ${rolle(P.sprite('hammer'), 'web.role.builders', px(s.projekte), t('web.role.builders.text'))}
          ${rolle(P.sprite('glocke'), 'web.role.guards', px(s.deadlines_faellig), t(s.flugrouten ? 'web.role.guards.routes' : 'web.role.guards.noroutes'))}
          ${rolle(P.sprite('topf'), 'web.role.foragers', px(s.gewohnheiten.length), t('web.role.foragers.text'), gew)}
        </div>
        <section class="karte"><div class="zeile weit"><h2>${P.sprite('kalender')} ${esc(t('r.cal.title'))}</h2>
          ${s.termine.length ? `<button class="knopf zweit klein-knopf" type="button" data-tun="melden" ${s.flugrouten ? '' : 'disabled'} title="${esc(s.flugrouten ? '' : t('r.cal.noroutes'))}">${P.sprite('glocke')}${esc(t('web.btn.notify'))}</button>` : ''}</div>
          ${termine}<p class="hinweis">${esc(t('web.cal.hint'))}</p></section>
        <section class="karte"><h2>${esc(t('web.recommend.title'))}</h2>
          <div class="schalter" role="group" aria-label="${esc(t('web.recommend.title'))}">
            ${['para', 'johnny', 'dewey'].map((k) => `<button type="button" data-tun="empfehlung" data-wert="${k}" aria-pressed="${S.empfehlung && S.empfehlung.strategie === k ? 'true' : 'false'}">${esc(t('web.recommend.' + k))}</button>`).join('')}
          </div>${emp}</section>
      </div>`;
  }

  // -- Wachstafel & Gedächtnis ------------------------------------------------
  async function seiteWachstafel() {
    if (!projekt()) return ohneProjekt();
    const [w, g] = await Promise.all([lesen('wachstafel'), lesen('gedaechtnis').catch(() => null)]);
    const regeln = w.regeln.length ? w.regeln.map((r) => `<div class="regel"><span class="stichwort">${esc(r.stichwort)}</span><span aria-hidden="true">→</span><b>${esc(r.wabe.name)}</b></div>`).join('')
      : `<p class="leise">${esc(t('web.rules.none'))}</p>`;
    const refl = S.reflexion ? `<section class="karte" aria-labelledby="refl-titel"><h2 id="refl-titel">${esc(t('r.reflect.title'))}</h2>
      ${S.reflexion.regeln.length ? `<div>${S.reflexion.regeln.map((r) => `<div class="regel"><span class="stichwort">${esc(r.stichwort)}</span><span aria-hidden="true">→</span><b>${esc(r.wabe.name)}</b>
        <span class="leise klein">${esc(t('web.rules.from', { n: r.anzahl }))}${r.statt ? ' · ' + esc(t('r.reflect.instead', { alt: r.statt.name }).trim()) : ''}</span></div>`).join('')}</div>
        <div class="zeile abstand"><button class="knopf" type="button" data-tun="ritzen">${P.sprite('stift')}${esc(t('web.btn.inscribe'))}</button>
        <button class="knopf zweit" type="button" data-tun="reflexion-weg">${esc(t('web.btn.discard'))}</button></div>`
        : `<p class="leise">${esc(t('r.reflect.few'))}</p>`}</section>` : '';
    const ged = g ? `<section class="karte"><h2>${esc(t('web.memory.title'))}</h2>
      <p>${esc(t('web.memory.vectors', { n: g.vektoren }))}</p>
      ${g.drift ? `<p class="chip frage">${esc(t('r.mem.drift', { drift: g.drift }))}</p>` : ''}
      <div class="zeile">${g.waben.map((x) => `<span class="chip">${esc(x.name)}</span>`).join('')}</div>
      ${g.vorschlaege.length ? `<h3 class="abstand">${esc(t('web.memory.proposals'))}</h3>${g.vorschlaege.map((v) => `<div class="regel"><span class="mit-symbol">${P.sprite('wabe', 'symbol')}<span>${esc(v.text)}</span></span>
        <button class="knopf zweit klein-knopf" type="button" data-tun="gedaechtnis-ok" data-slug="${esc(v.slug)}">${esc(t('web.btn.accept_short'))}</button></div>`).join('')}` : ''}
      <div class="zeile abstand"><button class="knopf leise-knopf" type="button" data-tun="gedaechtnis-neu">${esc(t('web.btn.rebuild'))}</button></div>
      <p class="hinweis">${esc(t('help.d.memory'))}</p></section>` : '';
    return `${seitenKopf('web.nav.rules', 'web.nav.rules.k')}
      <div class="stapel">
        <section class="wachs" aria-labelledby="wachs-titel"><div class="zeile weit"><h2 id="wachs-titel">${P.sprite('tafel')} ${esc(t('r.rules.title'))}</h2>
          <span class="leise klein">${esc(t('web.rules.corrections', { n: w.korrekturen }))}</span></div>
          <div id="regeln">${regeln}</div></section>
        <p class="hinweis">${esc(t('web.rules.safe'))}</p>
        <div class="zeile">
          <button class="knopf" type="button" data-tun="reflexion">${P.sprite('krone')}${esc(t('web.btn.reflect'))}</button>
          <button class="knopf leise-knopf" type="button" data-tun="abwischen" ${w.vorhanden ? '' : 'disabled'}>${esc(t('web.btn.wipe'))}</button>
        </div>
        ${refl}${ged}
      </div>`;
  }

  // -- Quarantäne ---------------------------------------------------------------
  async function seiteQuarantaene() {
    if (!projekt()) return ohneProjekt();
    const q = await lesen('quarantaene');
    const eintraege = q.eintraege.length ? `<div class="tabelle-huelle"><table class="liste"><tbody>${q.eintraege.map((r) => `<tr>
        <td><b>${esc(r.titel || r.datei)}</b><div class="datei leise">${esc(r.datei)}</div></td>
        <td><button class="knopf zweit klein-knopf" type="button" data-tun="zurueckholen" data-id="${esc(r.id)}">${P.sprite('rueckflug')}${esc(t('web.btn.restore'))}</button></td></tr>`).join('')}</tbody></table></div>`
      : leer(P.sprite('kiste'), t('r.trash.empty'));
    const dubletten = q.dubletten.length ? `<div class="tabelle-huelle"><table class="liste"><tbody>${q.dubletten.map((d) => `<tr><td class="datei">${esc(d.datei)}</td>
        <td class="leise">${esc(t('web.trash.original', { orig: d.original, cat: d.wabe.name }))}</td></tr>`).join('')}</tbody></table></div>
        <div class="zeile abstand"><button class="knopf zweit" type="button" data-tun="dubletten" data-n="${q.dubletten.length}">${esc(t('web.btn.dups', { n: q.dubletten.length }))}</button></div>`
      : `<p class="leise">${esc(t('r.dup.none'))}</p>`;
    return `${seitenKopf('web.nav.trash', 'web.nav.trash.k')}
      <div class="stapel">
        <p>${esc(t('web.trash.explain'))}</p>
        <section class="karte"><h2>${esc(t('web.trash.items'))}</h2>${eintraege}</section>
        <section class="karte"><h2>${esc(t('web.trash.dups'))}</h2><p class="hinweis">${esc(t('web.trash.dups.hint'))}</p>${dubletten}</section>
        <section class="karte gefahrenzone"><h2>${esc(t('web.trash.danger'))}</h2>
          <p>${esc(t('web.trash.danger.text', { n: q.dateien.length }))}</p>
          <button class="knopf gefahr" type="button" data-tun="leeren" data-n="${q.dateien.length}" ${q.dateien.length ? '' : 'disabled'}>${esc(t('web.btn.empty'))}</button>
        </section>
      </div>`;
  }

  // -- Werkstatt ----------------------------------------------------------------
  function schalter(name, werte, aktiv) {
    return `<div class="schalter" role="group">${werte.map(([wert, key]) =>
      `<button type="button" data-tun="${name}" data-wert="${esc(wert)}" aria-pressed="${String(wert) === String(aktiv) ? 'true' : 'false'}">${esc(t(key))}</button>`).join('')}</div>`;
  }

  // Sparmodus und Lokal entscheiden mit BeeNara anders — das soll man bei der Wahl sehen.
  const bnHinweis = (modus) => (modus !== 'openrouter' && S.z.beenara && S.z.beenara.bereit
    ? `<small>${esc(t('web.bn.mode_note'))}</small>` : '');

  // Ollama (Modus Lokal): Sprachmodell und Gedächtnis-Modell (RAG). Den Stand weiß nur der lokale
  // Ollama-Server — läuft er nicht, dauert die Frage bis zu 1,5 s. Darum zeichnet die Werkstatt die
  // Karte erst ohne Stand und setzt ihn nach (S.ollama); 'Erneut prüfen' und 'Verfügbarkeit
  // prüfen' fragen neu.
  const statusZeile = (z) => `<p class="mit-symbol ${z.art === 'ask' ? '' : 'leise'}">${symbol(z.emoji, z.art)}<span>${esc(ohneEmoji(z.text))}</span></p>`;
  const gbText = (gb) => (einst().sprache === 'en' ? String(gb) : String(gb).replace('.', ','));

  function ollamaModell(m) {
    const sprache = m.rolle === 'sprache';
    return `<div class="abstand"><div class="zeile weit"><h3 class="mit-symbol">${P.sprite(sprache ? 'chip' : 'gehirn', 'symbol')}<span>${esc(t(sprache ? 'om.rolle.sprache' : 'om.rolle.gedaechtnis'))}</span></h3>
        <span class="chip ${m.vorhanden ? 'wache' : 'aus'}">${esc(t(m.vorhanden ? 'web.om.chip.ready' : 'web.bn.chip.missing'))}</span></div>
      <p class="hinweis">${esc(t(sprache ? 'web.om.sprache.text' : 'web.om.gedaechtnis.text'))}</p>
      ${m.zeilen.map(statusZeile).join('')}
      ${m.vorhanden ? '' : `<div class="zeile abstand"><button class="knopf" type="button" data-tun="om-laden" data-rolle="${esc(m.rolle)}" data-modell="${esc(m.modell)}">${esc(t('web.btn.om_pull', { gb: gbText(m.gb) }))}</button></div>`}</div>`;
  }

  function ollamaKarte(om) {
    const alle = om && om.erreichbar && om.modelle.every((m) => m.vorhanden);
    const chip = !om ? ['frage', 'web.om.chip.checking'] : !om.erreichbar ? ['aus', 'web.om.chip.offline']
      : alle ? ['wache', 'web.om.chip.all'] : ['frage', 'web.bn.chip.incomplete'];
    const inhalt = !om ? '' : !om.erreichbar
      ? `${om.modelle[0].zeilen.map(statusZeile).join('')}
        <div class="zeile abstand"><button class="knopf zweit klein-knopf" type="button" data-tun="om-pruefen">${esc(t('web.btn.om_check'))}</button></div>`
      : om.modelle.map(ollamaModell).join('');
    return `<section class="karte" id="om-karte" aria-labelledby="om-titel"><div class="zeile weit"><h2 id="om-titel" class="mit-symbol">${P.sprite('haus', 'symbol')}<span>${esc(t('om.title'))}</span></h2>
        <span class="chip ${chip[0]}">${esc(t(chip[1]))}</span></div>
      <p class="hinweis">${esc(t('om.what'))}</p>
      ${inhalt}</section>`;
  }

  let ollamaFrage = null;
  let ollamaZiel = '';                          // welches Modell gerade lädt (Lauftext)
  function ollamaNachladen() {
    if (S.ollama || ollamaFrage) return;
    ollamaFrage = lesen('ollama_modelle').then((om) => {
      S.ollama = om;
      const karte = $('#om-karte');
      if (!karte || S.lauf) return;             // Seite gewechselt oder ein Lauf zeigt hier
      karte.outerHTML = ollamaKarte(om);
      P.schrift($('#om-karte'));
      stileAnwenden($('#om-karte'));
    }).catch(() => {}).finally(() => { ollamaFrage = null; });
  }

  async function seiteWerkstatt() {
    setTimeout(ollamaNachladen);                // erst wenn die Seite steht
    const w = await lesen('werkstatt');
    const e = w.einstellungen;
    const p = w.projekt;
    const modi = S.modi;
    const modusWahl = p ? [['offline', 'fr.ai.offline'], ['ollama', 'fr.ai.ollama'], ['openrouter', 'fr.ai.openrouter']].map(([wert, key]) => {
      const gesperrt = modi && !modi[wert];
      return `<label class="wahl ${gesperrt ? 'gesperrt' : ''}"><input type="radio" name="modus" value="${wert}" data-modus ${p.modus === wert ? 'checked' : ''} ${gesperrt ? 'disabled' : ''}>
        <span>${esc(t(key))}${gesperrt ? `<small>${esc(t(wert === 'ollama' ? 'web.su.ollama_hint' : 'web.key.console'))}</small>` : bnHinweis(wert)}</span></label>`;
    }).join('') : '';
    const bn = w.beenara;
    const bnChip = bn.bereit ? ['wache', 'web.bn.chip.on'] : bn.grund === 'aus' ? ['aus', 'web.bn.chip.off']
      : bn.vorhanden || bn.angefangen ? ['frage', 'web.bn.chip.incomplete'] : ['aus', 'web.bn.chip.missing'];
    const bnUnfertig = !bn.vorhanden || bn.angefangen || bn.grund === 'version' || bn.grund === 'laufzeit';
    // BeeNara Big: derselbe Platz, für große Ordnerbäume — nur mit NVIDIA-GPU ab 8 GB.
    const bb = w.beenara_big;
    const bbChip = bb.bereit ? ['wache', 'web.bn.chip.on'] : bb.vorhanden || bb.angefangen ? ['frage', 'web.bn.chip.incomplete']
      : bb.gpu_grund ? ['aus', 'web.bb.chip.gpu'] : ['aus', 'web.bn.chip.missing'];
    const bbUnfertig = !bb.vorhanden || bb.angefangen || bb.grund === 'version' || bb.grund === 'laufzeit';
    const bigTeil = `<div class="abstand"><div class="zeile weit"><h3 class="mit-symbol">${P.sprite('biene', 'symbol')}<span>${esc(t('bb.title'))}</span></h3>
        <span class="chip ${bbChip[0]}">${esc(t(bbChip[1]))}</span></div>
      <p class="hinweis">${esc(t('bb.what'))}</p>
      ${bb.zeilen.map((z) => `<p class="mit-symbol ${z.art === 'ask' ? '' : 'leise'}">${symbol(z.emoji, z.art)}<span>${esc(ohneEmoji(z.text))}</span></p>`).join('')}
      <div class="zeile abstand">
        ${bbUnfertig ? `<button class="knopf ${bb.gpu_grund ? 'zweit' : ''}" type="button" data-tun="bb-laden">${esc(t(bb.vorhanden || bb.angefangen ? 'web.btn.bn_finish' : 'web.btn.bb_pull'))}</button>` : ''}
        ${bb.vorhanden || bb.angefangen ? `<button class="knopf zweit klein-knopf" type="button" data-tun="bb-entfernen" data-mb="${esc(bb.mb)}">${esc(t('web.btn.bn_remove'))}</button>` : ''}
      </div>
      <div class="feld abstand"><span>${esc(t('web.bb.modell'))}</span>${schalter('bb-modell', [['auto', 'web.bb.auto'], ['klein', 'web.bb.klein'], ['big', 'web.bb.big']], bb.modus)}
        <small class="leise">${esc(t('web.bb.modell.text'))}</small></div></div>`;
    const beenaraKarte = `<section class="karte" aria-labelledby="bn-titel"><div class="zeile weit"><h2 id="bn-titel">${esc(t('fr.bn.title'))}</h2>
        <span class="chip ${bnChip[0]}">${esc(t(bnChip[1]))}</span></div>
      <p class="hinweis">${esc(t('bn.what'))} ${esc(t('fr.bn.size', { repo: bn.repo, mb: bn.ungefaehr_mb }))}</p>
      ${bn.zeilen.map((z) => `<p class="mit-symbol ${z.art === 'ask' ? '' : 'leise'}">${symbol(z.emoji, z.art)}<span>${esc(ohneEmoji(z.text))}</span></p>`).join('')}
      <div class="zeile abstand">
        ${bnUnfertig ? `<button class="knopf" type="button" data-tun="bn-laden">${esc(t(bn.vorhanden || bn.angefangen ? 'web.btn.bn_finish' : 'web.btn.bn_pull'))}</button>` : ''}
        ${bn.vorhanden ? `<div class="feld"><span>${esc(t('web.bn.use'))}</span>${schalter('bn-schalten', [[true, 'nx.on'], [false, 'nx.off']], bn.an)}</div>` : ''}
        ${bn.vorhanden || bn.angefangen ? `<button class="knopf zweit klein-knopf" type="button" data-tun="bn-entfernen" data-mb="${esc(bn.mb)}">${esc(t('web.btn.bn_remove'))}</button>` : ''}
      </div>
      ${bn.vorhanden || bb.vorhanden ? `<div class="feld abstand"><span>${esc(t('web.bn.auto'))}</span>${schalter('bn-auto', [[true, 'nx.on'], [false, 'nx.off']], bn.auto_update)}
        <small class="leise">${esc(t('web.bn.auto.text'))}</small></div>` : ''}
      ${bigTeil}
      ${laufBlock()}</section>`;
    const checks = S.check ? `<table class="liste"><tbody>${S.check.map((c) => `<tr><td>${P.sprite(c.status === 'ok' ? 'haken' : c.status === 'warn' ? 'warnung' : 'kreuz', 'symbol')}<span class="sr-only">${esc(c.status)}</span></td>
      <td><b>${esc(c.titel)}</b></td><td class="klein">${esc(c.detail)}</td></tr>`).join('')}</tbody></table>` : '';
    return `${seitenKopf('web.nav.workshop', 'web.nav.workshop.k')}
      <div class="stapel">
        <section class="karte"><h2>${esc(t('web.ws.look'))}</h2>
          <div class="zeile weit"><div><b>${esc(t('web.ws.workmode'))}</b><p class="hinweis">${esc(t('web.ws.workmode.text'))}</p></div>
            <button class="knopf ${e.arbeitsmodus ? '' : 'zweit'}" type="button" data-tun="arbeitsmodus" aria-pressed="${e.arbeitsmodus}">${esc(t(e.arbeitsmodus ? 'web.ws.workmode.on' : 'web.ws.workmode.off'))}</button></div>
          <div class="raster-2 abstand">
            <div class="feld"><span>${esc(t('web.ws.theme'))}</span>${schalter('thema', [['dark', 'fr.short.dark'], ['light', 'fr.short.light'], ['auto', 'fr.short.auto']], e.thema)}
              <small class="leise">${esc(t('fr.theme.auto'))}</small></div>
            <div class="feld"><span>${esc(t('web.ws.language'))}</span>${schalter('sprache', [['de', 'web.lang.de'], ['en', 'web.lang.en']], e.sprache)}</div>
            <div class="feld"><span>${esc(t('web.ws.anim'))}</span>${schalter('anim', [['voll', 'web.anim.voll'], ['dezent', 'web.anim.dezent'], ['aus', 'web.anim.aus']], e.animationen)}
              <small class="leise">${esc(t('web.ws.anim.text'))}</small></div>
            <div class="feld"><span>${esc(t('web.ws.progress'))}</span>${schalter('fortschritt', [[true, 'nx.on'], [false, 'nx.off']], e.fortschritt)}
              <small class="leise">${esc(t('web.ws.progress.text'))}</small></div>
            <div class="feld"><span>${esc(t('web.ws.plain'))}</span>${schalter('klartext', [[true, 'nx.on'], [false, 'nx.off']], e.klartext)}
              <small class="leise">${esc(t('web.ws.plain.text'))}</small></div>
          </div></section>
        ${p ? `<section class="karte"><div class="zeile weit"><h2>${esc(t('web.ws.project'))}</h2>
            <button class="knopf leise-knopf klein-knopf" type="button" data-tun="modi-pruefen">${esc(t('web.btn.check_modes'))}</button></div>
          <h3>${esc(t('su.mode.q'))}</h3><div class="wahl-gruppe">${modusWahl}</div>
          <div class="raster-2 abstand">
            <div class="feld"><span>${esc(t('su.watch.q'))}</span>${schalter('wache-modus', [['off', 'web.watchmode.off'], ['notify', 'web.watchmode.notify'], ['move', 'web.watchmode.move']], p.wache)}</div>
            <div class="feld"><span>${esc(t('web.ws.enrich'))}</span>${schalter('nacherfassung', [[true, 'nx.on'], [false, 'nx.off']], p.nacherfassung)}
              <small class="leise">${esc(t('help.d.enrich'))}</small></div>
            <form class="feld" data-form="modell"><span>${esc(t('r.model.title'))}</span>
              <div class="zeile"><select name="modell">${w.sorten.map((s) => `<option value="${esc(s.id)}" ${s.id === w.modell ? 'selected' : ''}>${esc(s.kurz)} · ${esc(s.id)}</option>`).join('')}
              ${w.sorten.some((s) => s.id === w.modell) ? '' : `<option value="${esc(w.modell)}" selected>${esc(w.modell)}</option>`}</select>
              <button class="knopf zweit klein-knopf" type="submit">${esc(t('web.btn.save'))}</button></div>
              <small class="leise">${esc(t('web.ws.model_hint'))}</small></form>
          </div></section>` : ''}
        ${beenaraKarte}
        ${ollamaKarte(S.ollama)}
        <section class="karte"><h2>${esc(t('web.ws.access'))}</h2>
          <table class="liste"><tbody>
            <tr><td class="mit-symbol">${P.sprite('schluessel', 'symbol')}<b>${esc(t('r.key.title'))}</b></td><td>${w.schluessel.quelle ? `<span class="mono">${esc(w.schluessel.maskiert)}</span> <span class="leise klein">(${esc(t('web.key.' + w.schluessel.quelle))})</span>` : `<span class="leise">${esc(t('r.key.none'))}</span>`}</td><td><code>schluessel setzen</code></td></tr>
            <tr><td class="mit-symbol">${P.sprite('route', 'symbol')}<b>${esc(t('r.routes.title'))}</b></td><td>${['discord', 'email', 'kalender'].map((k) => `<span class="chip ${w.flugrouten[k] ? 'wache' : 'aus'}">${esc(t('web.routes.' + k))}</span>`).join(' ')}</td><td><code>flugrouten setup</code></td></tr>
          </tbody></table>
          <p class="hinweis">${esc(t('web.ws.access.text'))}</p></section>
        <section class="karte"><div class="zeile weit"><h2 class="mit-symbol">${P.sprite('zahnrad', 'symbol')}<span>${esc(t('web.ws.check'))}</span></h2>
          <button class="knopf zweit" type="button" data-tun="stock-check">${esc(t('web.btn.check'))}</button></div>
          <p class="hinweis">${esc(t('help.d.doctor'))}</p>${checks}</section>
        <section class="karte"><div class="zeile weit"><h2>${esc(t('projects.title'))}</h2>
          <a class="knopf zweit" href="#/einrichten">${esc(t('web.project.new'))}</a></div>
          ${(S.z.projekte || []).length ? `<table class="liste"><tbody>${S.z.projekte.map((pr) => `<tr><td><b>${esc(pr.name)}</b><div class="pfad">${esc(pr.pfad)}</div></td>
            <td>${pr.aktiv ? `<span class="chip honig">${esc(t('web.active'))}</span>` : `<button class="knopf zweit klein-knopf" type="button" data-tun="wechseln" data-pfad="${esc(pr.pfad)}">${esc(t('web.btn.open'))}</button>`}</td></tr>`).join('')}</tbody></table>`
            : `<p class="leise">${esc(t('r.projects.none'))}</p>`}</section>
        <p class="leise klein">PollySort v${esc(S.z.version)} · ${esc(t('web.ws.about'))}</p>
      </div>`;
  }

  // -- Einrichtung (Assistent) ------------------------------------------------
  function neueEinrichtung() {
    return { schritt: S.z && S.z.erststart ? 0 : 1, pfad: '', pruefung: null, anlegen: false, name: '', modus: 'offline',
      katWahl: 'vorschlag', vorschlag: null, aus: {}, extra: [], eigene: '', unterordner: null, subAn: {}, wache: 'off', fertig: null,
      // BeeNara: wie im Erststart der Konsole nur auf Zusage — ohne Haken lädt nichts.
      beenara: false };
  }

  const SCHRITTE = ['web.su.step.look', 'web.su.step.folder', 'web.su.step.name', 'web.su.step.mode',
    'web.su.step.combs', 'web.su.step.sub', 'web.su.step.watch', 'web.su.step.done'];

  function gewaehlteKategorien() {
    const e = S.e;
    if (e.katWahl === 'eigene') return e.eigene.split(',').map((k) => k.trim().toLowerCase()).filter(Boolean);
    if (e.katWahl === 'standard') return (e.pruefung && e.pruefung.standard || []).map((k) => k.key);
    const vor = (e.vorschlag ? e.vorschlag.vorschlag : []).filter((k) => !e.aus[k.key]).map((k) => k.key);
    return Array.from(new Set(vor.concat(e.extra)));
  }

  function seiteEinrichten() {
    if (!S.e) S.e = neueEinrichtung();
    const e = S.e;
    const erst = S.z.erststart;
    const zellen = SCHRITTE.map((k, i) => (i === 0 && !erst ? '' : P.zelle(i < e.schritt ? 1 : i === e.schritt ? 0.5 : 0))).join('');
    let inhalt = '';
    let weiter = true;
    switch (e.schritt) {
      case 0:
        inhalt = `<h2>${esc(t('web.su.look'))}</h2>
          <div class="feld"><span>${esc(t('web.ws.language'))}</span>${schalter('sprache', [['de', 'web.lang.de'], ['en', 'web.lang.en']], einst().sprache)}</div>
          <div class="feld abstand"><span>${esc(t('web.ws.theme'))}</span>${schalter('thema', [['dark', 'fr.short.dark'], ['light', 'fr.short.light'], ['auto', 'fr.short.auto']], einst().thema)}</div>
          <div class="feld abstand"><span>${esc(t('web.ws.workmode'))}</span><p class="hinweis">${esc(t('web.ws.workmode.text'))}</p>
            <button class="knopf ${einst().arbeitsmodus ? '' : 'zweit'}" type="button" data-tun="arbeitsmodus">${esc(t(einst().arbeitsmodus ? 'web.ws.workmode.on' : 'web.ws.workmode.off'))}</button></div>`;
        break;
      case 1: {
        const pr = e.pruefung;
        let info = '';
        if (pr) {
          if (pr.eingerichtet) {
            info = `<p class="chip honig">${esc(t('su.exists', { name: pr.name }))}</p>
              <div class="zeile abstand"><button class="knopf" type="button" data-tun="wechseln" data-pfad="${esc(pr.pfad)}">${esc(t('web.btn.open_existing'))}</button>
              <span class="leise klein">${esc(t('web.su.redo'))}</span></div>`;
          } else if (!pr.existiert) {
            info = `<label class="zeile"><input type="checkbox" id="anlegen" ${e.anlegen ? 'checked' : ''}> ${esc(t('web.su.create', { path: pr.pfad }))}</label>`;
            weiter = e.anlegen;
          } else if (!pr.ist_ordner) {
            info = `<p class="chip fehler">${esc(t('su.path.notdir', { path: pr.pfad }))}</p>`;
            weiter = false;
          } else {
            info = `<p class="chip wache">${esc(t('web.su.found', { n: pr.lose }))}</p>`;
          }
        } else weiter = false;
        inhalt = `<h2>${esc(t('web.su.folder'))}</h2><p>${esc(t('firstrun.what'))}</p>
          <form class="zeile" data-form="pfad"><label class="sr-only" for="pfad">${esc(t('su.path.ask'))}</label>
            <input type="text" id="pfad" value="${esc(e.pfad)}" placeholder="C:\\Users\\…\\Documents\\Büro" class="wachsen">
            <button class="knopf zweit" type="submit">${esc(t('web.btn.check_path'))}</button></form>
          <p class="hinweis">${esc(t('web.su.folder.hint'))}</p>${info}`;
        break;
      }
      case 2:
        inhalt = `<h2>${esc(t('web.su.name'))}</h2><label class="feld"><span>${esc(t('web.su.name.label'))}</span>
          <input type="text" id="name" value="${esc(e.name || e.pruefung.name)}"></label>`;
        break;
      case 3: {
        const m = S.modi;
        inhalt = `<h2>${esc(t('su.mode.q'))}</h2>${m ? '' : `<div class="spaeher">${P.biene('flattert')}</div><p class="leise">${esc(t('web.su.checking'))}</p>`}
          <div class="wahl-gruppe">${[['offline', 'fr.ai.offline'], ['ollama', 'fr.ai.ollama'], ['openrouter', 'fr.ai.openrouter']].map(([wert, key]) => {
            const gesperrt = m && !m[wert];
            return `<label class="wahl ${gesperrt ? 'gesperrt' : ''}"><input type="radio" name="su-modus" value="${wert}" ${e.modus === wert ? 'checked' : ''} ${gesperrt || !m ? 'disabled' : ''}>
              <span>${esc(t(key))}${m && m[wert] && wert !== 'offline' ? ` <small>${esc(t(wert === 'openrouter' ? 'fr.ai.keyset' : 'fr.ai.found'))}</small>` : ''}${gesperrt ? `<small>${esc(t(wert === 'ollama' ? 'web.su.ollama_hint' : 'web.key.console'))}</small>` : bnHinweis(wert)}</span></label>`;
          }).join('')}</div>
          ${S.z.beenara && !S.z.beenara.bereit ? `<div class="abstand"><b>${esc(t('fr.bn.title'))}</b>
            <p class="hinweis">${esc(t('fr.bn.what'))} ${esc(t('fr.bn.size', { repo: S.z.beenara.repo, mb: S.z.beenara.ungefaehr_mb }))}</p>
            <label class="zeile"><input type="checkbox" id="su-beenara" ${e.beenara ? 'checked' : ''}> ${esc(t('web.su.bn.label'))}</label></div>` : ''}`;
        weiter = !!m;
        break;
      }
      case 4: {
        const v = e.vorschlag;
        const liste = e.katWahl === 'vorschlag' ? (v ? `<p class="chip honig">${esc(t('su.scout.header', { total: v.gesamt, tag: t(v.ki ? 'su.scout.tag_ai' : 'su.scout.tag_heur'), note: '' }))}</p>
            <div class="vorschlag-liste abstand">${v.vorschlag.map((k) => `<div class="vorschlag ${e.aus[k.key] ? 'ab' : ''}">${P.zelle(1)}<b>${esc(k.name)}</b>
              <span class="leise">${k.anzahl}${k.vorhanden ? ' · ' + esc(t('su.scout.exists')) : ''}</span>
              <button class="knopf leise-knopf klein-knopf" type="button" data-tun="su-weg" data-kat="${esc(k.key)}">${esc(t(e.aus[k.key] ? 'web.btn.keep' : 'web.btn.remove'))}</button></div>`).join('')}
              ${e.extra.map((k) => `<div class="vorschlag">${P.zelle(0)}<b>${esc(k.charAt(0).toUpperCase() + k.slice(1))}</b><span class="leise">${esc(t('web.su.added'))}</span><span></span></div>`).join('')}</div>
            <form class="zeile abstand" data-form="su-extra"><input type="text" id="su-extra" placeholder="${esc(t('web.review.newcomb'))}" class="breite-s">
              <button class="knopf zweit klein-knopf" type="submit">${esc(t('web.btn.newcomb'))}</button></form>`
          : `<div class="spaeher" id="spaeher" hidden>${P.biene('flattert')}${P.biene('flattert')}${P.biene('flattert')}</div>
             <button class="knopf" type="button" data-tun="spaehen">${P.sprite('lupe')}${esc(t('web.btn.scout'))}</button>
             <p class="hinweis">${esc(t('web.su.scout.hint'))}</p>`)
          : e.katWahl === 'eigene' ? `<label class="feld"><span>${esc(t('web.su.cat.own.label'))}</span><input type="text" id="eigene" value="${esc(e.eigene)}" placeholder="rechnungen, vertraege, fotos"></label>`
            : `<div class="zeile">${(e.pruefung.standard || []).map((k) => `<span class="chip">${esc(k.name)}</span>`).join('')}</div>`;
        inhalt = `<h2>${esc(t('su.cat.q'))}</h2>
          <div class="schalter" role="group">${[['vorschlag', 'web.su.cat.propose'], ['standard', 'web.su.cat.standard'], ['eigene', 'web.su.cat.own']].map(([w, k]) =>
            `<button type="button" data-tun="su-kat" data-wert="${w}" aria-pressed="${e.katWahl === w}">${esc(t(k))}</button>`).join('')}</div>
          <div class="abstand">${liste}</div>`;
        weiter = e.katWahl !== 'vorschlag' || !!v;
        break;
      }
      case 5: {
        const u = e.unterordner;
        inhalt = `<h2>${esc(t('su.sub.q'))}</h2>${u ? (u.length ? `<div class="wahl-gruppe">${u.map((x) => `<label class="wahl"><input type="checkbox" data-sub="${esc(x.key)}" ${e.subAn[x.key] !== false ? 'checked' : ''}>
            <span><b>${esc(x.name)}</b> → <span class="mono">${esc(x.muster)}</span></span></label>`).join('')}</div>` : `<p class="leise">${esc(t('web.su.sub.none'))}</p>`)
          : `<div class="spaeher">${P.biene('flattert')}</div>`}`;
        weiter = !!u;
        break;
      }
      case 6:
        inhalt = `<h2>${esc(t('su.watch.q'))}</h2><div class="wahl-gruppe">${[['off', 'su.watch.off'], ['notify', 'su.watch.notify'], ['move', 'su.watch.move']].map(([w, k]) =>
          `<label class="wahl"><input type="radio" name="su-wache" value="${w}" ${e.wache === w ? 'checked' : ''}><span>${esc(t(k))}</span></label>`).join('')}</div>
          <p class="hinweis">${esc(t('web.su.watch.hint'))}</p>`;
        break;
      default: {
        if (e.fertig) {
          inhalt = `<div class="leer-zustand">${P.sprite('topf')}<h2 data-px="${esc(t('su.done.title'))}">${esc(t('su.done.title'))}</h2>
            <p>${esc(t('web.su.done', { name: e.fertig.name, n: e.fertig.waben }))}</p></div>
            ${e.beenara ? laufBlock() : ''}
            <div class="zeile">${e.fertig.lose ? `<button class="knopf gross" type="button" data-tun="su-einlagern">${esc(t('web.su.file_now', { n: e.fertig.lose }))}</button>
              <button class="knopf zweit" type="button" data-tun="su-vorschau">${esc(t('web.btn.preview'))}</button>` : ''}
              <a class="knopf zweit" href="#/zuhause">${esc(t('web.btn.home'))}</a></div>`;
          weiter = false;
          break;
        }
        const kats = gewaehlteKategorien();
        const sub = (e.unterordner || []).filter((x) => e.subAn[x.key] !== false && kats.includes(x.key));
        inhalt = `<h2>${esc(t('web.su.summary'))}</h2><table class="liste"><tbody>
          <tr><td>${esc(t('web.su.step.folder'))}</td><td class="mono">${esc(e.pruefung.pfad)}</td></tr>
          <tr><td>${esc(t('web.su.step.name'))}</td><td>${esc(e.name || e.pruefung.name)}</td></tr>
          <tr><td>${esc(t('web.su.step.mode'))}</td><td>${esc(t('mode.' + e.modus))}</td></tr>
          <tr><td>${esc(t('web.su.step.combs'))}</td><td>${kats.map((k) => `<span class="chip">${esc(k.charAt(0).toUpperCase() + k.slice(1))}</span>`).join(' ')}</td></tr>
          <tr><td>${esc(t('web.su.step.sub'))}</td><td>${sub.length ? sub.map((x) => `${esc(x.name)} → <span class="mono">${esc(x.muster)}</span>`).join('<br>') : '—'}</td></tr>
          <tr><td>${esc(t('web.su.step.watch'))}</td><td>${esc(t('su.watch.' + e.wache))}</td></tr>
          <tr><td>${esc(t('web.su.bn.row'))}</td><td>${esc(t(S.z.beenara && S.z.beenara.bereit ? 'web.su.bn.ready' : e.beenara ? 'web.su.bn.yes' : 'web.su.bn.no'))}</td></tr></tbody></table>`;
      }
    }
    const letzter = e.schritt >= 7;
    return `${seitenKopf('web.su.title', 'web.su.title.k')}
      <div class="assistent">
        <div class="schritte" aria-label="${esc(t('web.su.progress', { i: e.schritt + (erst ? 1 : 0), n: SCHRITTE.length - (erst ? 0 : 1) }))}">${zellen}
          <span>${esc(t(SCHRITTE[Math.min(e.schritt, 7)]))}</span></div>
        <section class="karte">${inhalt}
          ${e.fertig ? '' : `<div class="aktionen">
            <button class="knopf leise-knopf" type="button" data-tun="su-zurueck" ${e.schritt > (erst ? 0 : 1) ? '' : 'disabled'}>${esc(t('web.btn.back'))}</button>
            <button class="knopf ${letzter ? 'gross' : ''}" type="button" data-tun="${letzter ? 'su-fertig' : 'su-weiter'}" ${weiter ? '' : 'disabled'}>${esc(t(letzter ? 'web.btn.setup' : 'web.btn.next'))}</button>
          </div>`}
        </section>
        ${e.fertig ? '' : `<p class="hinweis">${esc(t('web.su.abort'))}</p>`}
      </div>`;
  }

  // ------------------------------------------------------------------ //
  //  Router
  // ------------------------------------------------------------------ //
  const SEITEN = {
    zuhause: seiteZuhause, flugloch: seiteFlugloch, rueckfragen: seiteRueckfragen, waben: seiteWaben,
    schwarm: seiteSchwarm, wachstafel: seiteWachstafel, quarantaene: seiteQuarantaene,
    werkstatt: seiteWerkstatt, einrichten: seiteEinrichten,
  };

  function routeLesen() {
    const teile = location.hash.replace(/^#\/?/, '').split('/').filter(Boolean);
    S.route = teile.length && SEITEN[teile[0]] ? teile : ['zuhause'];
  }

  let zeichnet = 0;
  async function seiteZeichnen(stumm) {
    const nr = ++zeichnet;
    const main = $('#inhalt');
    const fn = SEITEN[S.route[0]] || seiteZuhause;
    let html;
    try {
      html = await fn();
    } catch (e) {
      html = `<section class="karte">${leer(P.sprite('frage'), e.message || String(e))}</section>`;
    }
    if (nr !== zeichnet) return;               // eine neuere Navigation hat übernommen
    const fokus = document.activeElement && document.activeElement.id;
    main.innerHTML = `<div class="seite">${html}</div>`;
    P.schrift(main);
    stileAnwenden(main);
    if (S.route[0] === 'flugloch') laufZeichnen();
    if (fokus && stumm && $('#' + CSS.escape(fokus))) $('#' + CSS.escape(fokus)).focus();
    else if (!stumm) main.focus({ preventScroll: true });
    if (S.route[0] === 'einrichten') einrichtungNachher();
    document.title = `${t((NAV.flat().find((n) => n.id === S.route[0]) || { b: 'web.su.title' }).b)} · PollySort`;
  }

  async function zustandLaden() {
    try {
      S.z = await lesen('zustand');
      einstellungenAnwenden();
      if (S.z.beenara && S.z.beenara.aktualisiert) hintergrundZeigen();
    } catch (e) {
      if (e.status === 401) {
        $('#inhalt').innerHTML = `<div class="seite"><section class="karte">${leer(P.sprite('frage'), t('web.err.token'))}</section></div>`;
        throw e;
      }
      fehler(e);
    }
  }

  async function navigieren() {
    routeLesen();
    if (S.route[0] !== 'flugloch') S.ergebnis = null;   // ein altes Ergebnis wäre irreführend
    if (!projekt() && !['einrichten', 'werkstatt'].includes(S.route[0]) && S.z && S.z.erststart) {
      location.hash = '#/einrichten';
      return;
    }
    rahmenZeichnen();
    window.scrollTo(0, 0);
    await seiteZeichnen(false);
  }

  // ------------------------------------------------------------------ //
  //  Aktionen
  // ------------------------------------------------------------------ //
  async function vorschauStarten() {
    S.ergebnis = null;
    const erg = await arbeit('vorschau');
    if (erg) S.vorschau = erg.eingelagert || erg.rueckfragen || erg.plan.length ? erg : null;
    if (erg && !S.vorschau) hinweis({ titel: t('pl.nothing') });
    await seiteZeichnen(true);
    const k = $('#vorschau-karte');
    if (k) k.scrollIntoView({ behavior: animVoll() ? 'smooth' : 'auto', block: 'start' });
  }

  async function sortierenStarten(cache) {
    const turbo = $('#turbo') && $('#turbo').checked;
    S.vorschau = null;
    const erg = await arbeit(cache ? 'anwenden' : 'sortieren', cache ? {} : { turbo });
    if (erg) S.ergebnis = erg;
    await seiteZeichnen(true);
    const k = $('#ergebnis-karte');
    if (k) { k.scrollIntoView({ behavior: animVoll() ? 'smooth' : 'auto', block: 'start' }); }
    feiern(erg, k || $('#station-waben'));
  }

  async function rueckAntwort(kat) {
    const f = S.rueck.faelle[S.rueck.index];
    if (!f || !kat) return;
    try {
      const antwort = await tun('zuordnen', { id: f.id, kategorie: kat, quelle: 'review' });
      feiern({ spiel: antwort.spiel });
    } catch (e) { fehler(e); return; }
    S.rueck.faelle.splice(S.rueck.index, 1);
    if (S.rueck.index >= S.rueck.faelle.length) S.rueck.index = 0;
    await zustandLaden();
    rahmenZeichnen();
    const ort = $('.seite');
    ort.innerHTML = seitenKopf('web.nav.review', 'web.nav.review.k') + rueckKarte();
    P.schrift(ort);
    const l = $('#lernt');
    const w = S.rueck.waben.find((x) => x.key === kat);
    if (l) { l.textContent = t('web.review.learned', { cat: w ? w.name : kat }); l.classList.add('zeigen'); }
    if (!S.rueck.faelle.length) { funkeln($('.leer-zustand')); hinweis({ titel: t('web.review.alldone'), art: 'erfolg' }); }
  }

  function rueckWeiter() {
    if (!S.rueck.faelle.length) return;
    S.rueck.index = (S.rueck.index + 1) % S.rueck.faelle.length;
    const ort = $('.seite');
    ort.innerHTML = seitenKopf('web.nav.review', 'web.nav.review.k') + rueckKarte();
    P.schrift(ort);
  }

  function bestaetigen({ titel, text, ja, gefahr, eingabe }) {
    return new Promise((fertig) => {
      const d = $('#dialog');
      d.className = gefahr ? 'gefahr' : '';
      d.innerHTML = `<form method="dialog"><h2>${esc(titel)}</h2><p>${esc(text)}</p>
        ${eingabe ? `<label class="feld"><span>${esc(eingabe.label)}</span><input type="${eingabe.typ || 'text'}" id="dialog-eingabe" autocomplete="off" inputmode="numeric"></label>` : ''}
        <div class="aktionen"><button class="knopf zweit" value="nein" type="submit">${esc(t('web.btn.cancel'))}</button>
        <button class="knopf ${gefahr ? 'gefahr' : ''}" value="ja" type="submit">${esc(ja || t('web.btn.ok'))}</button></div></form>`;
      d.addEventListener('close', function zu() {
        d.removeEventListener('close', zu);
        const wert = $('#dialog-eingabe') ? $('#dialog-eingabe').value : true;
        fertig(d.returnValue === 'ja' ? wert : null);
      });
      d.showModal();
      const feld = $('#dialog-eingabe');
      if (feld) feld.focus();
    });
  }

  // Ergebnis von 'beenara_laden' (null = Fehler, schon gemeldet) als Hinweis unten rechts.
  function bnMelden(r) {
    if (!r) return;
    if (r.ok) hinweis({ titel: t('web.toast.bn.ready'), text: t('web.toast.bn.ready.text'), art: 'erfolg' });
    else hinweis({ titel: t('web.toast.bn.failed'), text: t('web.toast.bn.failed.text'), art: 'fehler' });
  }

  async function einstellen(daten) {
    try {
      const e = await tun('einstellungen', daten);
      S.z.einstellungen = e;
      if (daten.sprache) {
        const texte = await lesen('texte');
        T = texte.texte;
        S.z.sprache = texte.sprache;
      }
      einstellungenAnwenden();
      rahmenZeichnen();
      await seiteZeichnen(true);
    } catch (e) { fehler(e); }
  }

  const bool = (w) => w === true || w === 'true';

  const AKTIONEN = {
    'vorschau-start': () => { location.hash = '#/flugloch'; setTimeout(vorschauStarten, 60); },
    'sortieren-start': () => { location.hash = '#/flugloch'; setTimeout(() => sortierenStarten(false), 60); },
    vorschau: () => vorschauStarten(),
    sortieren: () => sortierenStarten(false),
    anwenden: () => sortierenStarten(true),
    verwerfen: async () => { S.vorschau = null; try { await tun('verwerfen'); } catch (e) { fehler(e); } seiteZeichnen(true); },
    importieren: async () => {
      const ordner = $('#import-ordner').value.trim();
      if (!ordner) return;
      const erg = await arbeit('importieren', { ordner });
      if (erg) { S.ergebnis = erg; await seiteZeichnen(true); feiern(erg, $('#ergebnis-karte')); }
    },
    scan: async () => {
      const r = await arbeit('scan');
      if (r) hinweis({ titel: t('sw.title'), text: t('web.scan.result', r), art: 'erfolg', icon: P.sprite('lupe') });
      seiteZeichnen(true);
    },
    wache: async () => {
      try { S.z.wache = await tun('wache_schalten', { an: !(S.z.wache && S.z.wache.aktiv) }); rahmenZeichnen(); } catch (e) { fehler(e); }
    },
    rueckflug: async (el) => {
      try {
        const r = await tun('rueckflug');
        if (r.nichts) hinweis({ titel: t('r.undo.none') });
        else {
          fliegen(el, $('#logo'), { links: true });
          hinweis({ titel: t('web.undo.done'), text: t('r.undo.ok', { name: r.datei, folder: r.ordner }), icon: P.sprite('rueckflug') });
        }
        await zustandLaden(); rahmenZeichnen(); seiteZeichnen(true);
      } catch (e) { fehler(e); }
    },
    'rueck-wahl': (el) => rueckAntwort(el.dataset.kat),
    'rueck-ok': () => { const f = S.rueck.faelle[S.rueck.index]; if (f && f.vorschlag.key !== '_unassigned') rueckAntwort(f.vorschlag.key); },
    'rueck-skip': () => rueckWeiter(),
    'rueck-oeffnen': async () => { const f = S.rueck.faelle[S.rueck.index]; if (f) { try { await tun('oeffnen', { id: f.id }); } catch (e) { fehler(e); } } },
    oeffnen: async (el) => { try { await tun('oeffnen', { id: el.dataset.id }); } catch (e) { fehler(e); } },
    analysieren: async (el) => {
      const r = await arbeit('analysieren', { id: el.dataset.id });
      if (!r) return;
      hinweis({ titel: t('r.reana.done', { title: r.titel }), icon: P.sprite('lupe') });
      if (r.umsortieren_moeglich && await bestaetigen({ titel: t('web.reana.title'), text: t('web.reana.text', { old: r.alt.name, new: r.neu.name }), ja: t('web.btn.move') })) {
        try { await tun('zuordnen', { id: r.id, kategorie: r.neu.key, quelle: 'analysiere' }); } catch (e) { fehler(e); }
      }
      seiteZeichnen(true);
    },
    papierkorb: async (el) => {
      try { const r = await tun('papierkorb', { id: el.dataset.id }); hinweis({ titel: t('r.trash.moved', { name: r.datei }), icon: P.sprite('kiste') }); } catch (e) { fehler(e); }
      await zustandLaden(); rahmenZeichnen(); seiteZeichnen(true);
    },
    zurueckholen: async (el) => {
      try { const r = await tun('zurueckholen', { id: el.dataset.id }); hinweis({ titel: t('r.restore.ok', { name: r.datei }), art: 'erfolg', icon: P.sprite('rueckflug') }); } catch (e) { fehler(e); }
      await zustandLaden(); rahmenZeichnen(); seiteZeichnen(true);
    },
    dubletten: async (el) => {
      const ok = await bestaetigen({ titel: t('web.trash.dups'), text: t('web.dup.confirm', { n: el.dataset.n }), ja: t('web.btn.dups', { n: el.dataset.n }) });
      if (!ok) return;
      try { const r = await tun('dubletten_aufraeumen'); hinweis({ titel: t('r.dup.moved', { n: r.verschoben }), icon: P.sprite('kiste') }); } catch (e) { fehler(e); }
      seiteZeichnen(true);
    },
    leeren: async (el) => {
      const n = el.dataset.n;
      const wert = await bestaetigen({ titel: t('web.trash.danger'), text: t('web.trash.confirm', { n }), ja: t('web.btn.empty'), gefahr: true, eingabe: { label: t('web.trash.type', { n }), typ: 'text' } });
      if (wert == null) return;
      if (String(wert).trim() !== String(n)) { hinweis({ titel: t('r.cancelled'), text: t('web.err.confirm_count', { n }), art: 'fehler' }); return; }
      try { const r = await tun('leeren', { anzahl: Number(wert) }); hinweis({ titel: t('r.trash.deleted', { n: r.geloescht }) }); } catch (e) { fehler(e); }
      await zustandLaden(); seiteZeichnen(true);
    },
    reflexion: async () => { try { S.reflexion = await tun('reflexion_vorschau'); } catch (e) { fehler(e); } seiteZeichnen(true); },
    'reflexion-weg': async () => { S.reflexion = null; hinweis({ titel: t('r.reflect.discarded') }); seiteZeichnen(true); },
    ritzen: async () => {
      try {
        const r = await tun('reflexion_ritzen');
        S.reflexion = null;
        await seiteZeichnen(true);
        $$('#regeln .regel').forEach((el, i) => { el.classList.add('geritzt'); el.style.animationDelay = `${i * 0.12}s`; });
        hinweis({ titel: t('r.reflect.saved', { n: r.geritzt }), art: 'erfolg', icon: P.sprite('tafel') });
        await zustandLaden(); rahmenZeichnen();
      } catch (e) { fehler(e); }
    },
    abwischen: async () => {
      if (!await bestaetigen({ titel: t('web.btn.wipe'), text: t('web.rules.confirm'), ja: t('web.btn.wipe'), gefahr: true })) return;
      try { await tun('wachstafel_leeren'); hinweis({ titel: t('r.rules.cleared') }); } catch (e) { fehler(e); }
      seiteZeichnen(true);
    },
    'gedaechtnis-ok': async (el) => { try { const r = await tun('gedaechtnis_uebernehmen', { slug: el.dataset.slug }); hinweis({ titel: r.text, art: 'erfolg' }); } catch (e) { fehler(e); } seiteZeichnen(true); },
    'gedaechtnis-neu': async () => {
      const kosten = projekt() && projekt().modus === 'openrouter' ? ' ' + t('r.mem.cost') : '';
      if (!await bestaetigen({ titel: t('web.btn.rebuild'), text: t('web.memory.rebuild') + kosten, ja: t('web.btn.rebuild') })) return;
      const r = await arbeit('gedaechtnis_neu');
      if (r) hinweis({ titel: t('r.mem.rebuilt', { ok: r.ok }), art: 'erfolg' });
      seiteZeichnen(true);
    },
    melden: async () => { const r = await arbeit('kalender_melden'); if (r) hinweis({ titel: t('web.cal.sent', { n: r.faellig }), icon: P.sprite('glocke') }); },
    empfehlung: async (el) => { try { S.empfehlung = await tun('empfehlung', { strategie: el.dataset.wert }); } catch (e) { fehler(e); } seiteZeichnen(true); },
    'unterordner-aus': async (el) => { try { await tun('unterordner', { kategorie: el.dataset.kat, muster: '' }); } catch (e) { fehler(e); } seiteZeichnen(true); },
    thema: (el) => einstellen({ thema: el.dataset.wert }),
    sprache: (el) => einstellen({ sprache: el.dataset.wert }),
    anim: (el) => einstellen({ animationen: el.dataset.wert }),
    fortschritt: (el) => einstellen({ fortschritt: bool(el.dataset.wert) }),
    klartext: (el) => einstellen({ klartext: bool(el.dataset.wert) }),
    arbeitsmodus: () => einstellen({ arbeitsmodus: !einst().arbeitsmodus }),
    'wache-modus': async (el) => { try { await tun('projekt_einstellen', { wache: el.dataset.wert }); await zustandLaden(); rahmenZeichnen(); seiteZeichnen(true); } catch (e) { fehler(e); } },
    nacherfassung: async (el) => { try { await tun('projekt_einstellen', { nacherfassung: bool(el.dataset.wert) }); seiteZeichnen(true); } catch (e) { fehler(e); } },
    'modi-pruefen': async () => { try { S.modi = await tun('modi_pruefen'); } catch (e) { fehler(e); } S.ollama = null; seiteZeichnen(true); },
    'stock-check': async () => { try { S.check = (await tun('stock_check')).checks; } catch (e) { fehler(e); } seiteZeichnen(true); },
    // -- BeeNara (Werkstatt) --
    'bn-laden': async () => { bnMelden(await arbeit('beenara_laden')); seiteZeichnen(true); },
    'bn-schalten': async (el) => {
      try { await tun('beenara_schalten', { an: bool(el.dataset.wert) }); } catch (e) { fehler(e); }
      await zustandLaden(); seiteZeichnen(true);
    },
    'bn-auto': async (el) => {
      try { await tun('beenara_auto_update', { an: bool(el.dataset.wert) }); } catch (e) { fehler(e); }
      await zustandLaden(); seiteZeichnen(true);
    },
    'bn-entfernen': async (el) => {
      if (!await bestaetigen({ titel: t('web.btn.bn_remove'), text: t('web.bn.remove.text', { mb: el.dataset.mb }), ja: t('web.btn.bn_remove'), gefahr: true })) return;
      try { await tun('beenara_entfernen'); hinweis({ titel: t('bn.remove.done') }); } catch (e) { fehler(e); }
      await zustandLaden(); seiteZeichnen(true);
    },
    // -- BeeNara Big (Werkstatt) --
    'bb-laden': async () => {
      const r = await arbeit('beenara_big_laden');
      if (r) hinweis(r.ok ? { titel: t('web.toast.bb.ready'), text: t('web.toast.bb.ready.text'), art: 'erfolg' }
        : { titel: t('web.toast.bb.failed'), text: t('web.toast.bn.failed.text'), art: 'fehler' });
      seiteZeichnen(true);
    },
    'bb-modell': async (el) => {
      try { await tun('beenara_modell', { modell: el.dataset.wert }); } catch (e) { fehler(e); }
      seiteZeichnen(true);
    },
    'bb-entfernen': async (el) => {
      if (!await bestaetigen({ titel: t('web.btn.bn_remove'), text: t('web.bb.remove.text', { mb: el.dataset.mb }), ja: t('web.btn.bn_remove'), gefahr: true })) return;
      try { await tun('beenara_big_entfernen'); hinweis({ titel: t('bb.remove.done') }); } catch (e) { fehler(e); }
      await zustandLaden(); seiteZeichnen(true);
    },
    // -- Ollama-Modelle: Sprachmodell und Gedächtnis-Modell (Werkstatt) --
    'om-laden': async (el) => {
      // Der Fortschritt hat einen Platz auf der Seite (#lauf, in der BeeNara-Karte). Für diesen
      // Download wandert er in die Ollama-Karte — dort zeigt und sperrt er.
      const lauf = $('#lauf');
      const karte = $('#om-karte');
      if (lauf && karte && !S.lauf) karte.appendChild(lauf);
      const { rolle, modell } = el.dataset;
      ollamaZiel = modell;
      const r = await arbeit('ollama_modell_laden', { rolle });
      if (r) {
        S.ollama = r.ollama;
        hinweis(r.ok ? { titel: t('web.toast.om.ready', { modell }), art: 'erfolg',
          text: t(rolle === 'sprache' ? 'web.toast.om.ready.sprache' : 'web.toast.om.ready.gedaechtnis') }
          : { titel: t('web.toast.om.failed', { modell }), text: t('web.toast.bn.failed.text'), art: 'fehler' });
      }
      seiteZeichnen(true);
    },
    'om-pruefen': () => { S.ollama = null; seiteZeichnen(true); },
    wechseln: async (el) => {
      try {
        const r = await tun('wechseln', { pfad: el.dataset.pfad });
        if (r.einrichten) { S.e = neueEinrichtung(); S.e.pfad = r.pfad; location.hash = '#/einrichten'; return; }
        S.vorschau = null; S.ergebnis = null; S.rueck.index = 0; S.e = null;
        await zustandLaden();
        location.hash = '#/zuhause';
        rahmenZeichnen(); seiteZeichnen(false);
      } catch (e) { fehler(e); }
    },
    // -- Assistent --
    'su-weiter': () => einrichtungWeiter(),
    'su-zurueck': () => { S.e.schritt = Math.max(S.z.erststart ? 0 : 1, S.e.schritt - 1); seiteZeichnen(true); },
    'su-kat': (el) => { S.e.katWahl = el.dataset.wert; seiteZeichnen(true); },
    'su-weg': (el) => { S.e.aus[el.dataset.kat] = !S.e.aus[el.dataset.kat]; seiteZeichnen(true); },
    spaehen: async () => {
      const sp = $('#spaeher'); if (sp) sp.hidden = false;
      const r = await arbeit('waben_vorschlagen', { pfad: S.e.pruefung.pfad, modus: S.e.modus });
      if (r) S.e.vorschlag = r;
      seiteZeichnen(true);
    },
    'su-fertig': async () => {
      const e = S.e;
      const kats = gewaehlteKategorien();
      const unterordner = {};
      (e.unterordner || []).forEach((x) => { if (e.subAn[x.key] !== false && kats.includes(x.key)) unterordner[x.key] = x.muster; });
      const r = await arbeit('einrichten', { pfad: e.pruefung.pfad, name: e.name || e.pruefung.name, modus: e.modus, kategorien: kats, unterordner, wache: e.wache, anlegen: e.anlegen });
      if (r) { e.fertig = r; await zustandLaden(); rahmenZeichnen(); }
      await seiteZeichnen(true);
      // Zugesagt im Schritt „Modus" — erst jetzt, damit die Einrichtung nie am Download hängt.
      if (r && e.beenara && !(S.z.beenara || {}).bereit) {
        bnMelden(await arbeit('beenara_laden'));
        await seiteZeichnen(true);
      }
    },
    'su-einlagern': () => { S.e = null; location.hash = '#/flugloch'; setTimeout(() => sortierenStarten(false), 80); },
    'su-vorschau': () => { S.e = null; location.hash = '#/flugloch'; setTimeout(vorschauStarten, 80); },
  };

  async function einrichtungWeiter() {
    const e = S.e;
    if (e.schritt === 2) e.name = $('#name').value.trim();
    if (e.schritt === 3) {
      const m = $('input[name="su-modus"]:checked'); if (m) e.modus = m.value;
      const bn = $('#su-beenara'); if (bn) e.beenara = bn.checked;
    }
    if (e.schritt === 4 && e.katWahl === 'eigene') e.eigene = $('#eigene').value;
    if (e.schritt === 4 && !gewaehlteKategorien().length) { hinweis({ titel: t('web.su.cat.empty'), art: 'fehler' }); return; }
    if (e.schritt === 5) $$('[data-sub]').forEach((c) => { e.subAn[c.dataset.sub] = c.checked; });
    if (e.schritt === 6) { const w = $('input[name="su-wache"]:checked'); if (w) e.wache = w.value; }
    e.schritt += 1;
    if (e.schritt === 3 && !S.modi) {
      seiteZeichnen(true);
      try { S.modi = await tun('modi_pruefen'); } catch (err) { S.modi = { offline: true, ollama: false, openrouter: false }; }
      if (!S.modi[e.modus]) e.modus = S.modi.ollama ? 'ollama' : 'offline';
    }
    if (e.schritt === 4 && e.katWahl === 'vorschlag' && e.pruefung && !e.pruefung.lose) e.katWahl = 'standard';
    if (e.schritt === 5) {
      e.unterordner = null;
      seiteZeichnen(true);
      try { e.unterordner = (await tun('unterordner_vorschlagen', { kategorien: gewaehlteKategorien(), modus: e.modus })).vorschlag; } catch (err) { e.unterordner = []; }
    }
    seiteZeichnen(true);
  }

  function einrichtungNachher() {
    const an = $('#anlegen');
    if (an) an.addEventListener('change', () => { S.e.anlegen = an.checked; seiteZeichnen(true); });
    if (S.e && S.e.schritt === 1 && !S.e.pruefung && $('#pfad')) {
      if (S.e.pfad) FORMULARE.pfad($('[data-form="pfad"]')); else $('#pfad').focus();
    }
  }

  // ------------------------------------------------------------------ //
  //  Formulare, Ziehen & Ablegen, Tastatur
  // ------------------------------------------------------------------ //
  const FORMULARE = {
    'rueck-neu': (f) => { const k = $('#rueck-neu', f).value.trim(); if (k) rueckAntwort(k.toLowerCase()); },
    suche: (f) => { const q = $('#suche', f).value.trim(); location.hash = q ? `#/waben/_suche/${encodeURIComponent(q)}` : '#/waben'; },
    unterordner: async (f) => {
      try { await tun('unterordner', { kategorie: f.dataset.kat, muster: f.elements.muster.value }); hinweis({ titel: t('r.sub.set', { cat: f.dataset.kat, pattern: f.elements.muster.value || '—' }) }); } catch (e) { fehler(e); }
      seiteZeichnen(true);
    },
    wabenbau: async (f) => {
      const r = await arbeit('wabenbau', { kategorie: f.dataset.kat, wer: f.elements.wer.value, ziel: f.elements.ziel.value, deadline: f.elements.deadline.value });
      if (r) { S.wabenbau = r; hinweis({ titel: t(r.komplett ? 'r.charter.done' : 'web.charter.built'), art: 'erfolg', icon: P.sprite('hammer') }); }
      seiteZeichnen(true);
    },
    modell: async (f) => { try { await tun('modell', { name: f.elements.modell.value }); hinweis({ titel: t('r.model.set', { model: f.elements.modell.value }) }); } catch (e) { fehler(e); } },
    pfad: async (f) => {
      const pfad = $('#pfad', f).value.trim();
      S.e.pfad = pfad;
      try { S.e.pruefung = await tun('einrichtung_pruefen', { pfad }); S.e.name = S.e.name || S.e.pruefung.name; } catch (e) { S.e.pruefung = null; fehler(e); }
      seiteZeichnen(true);
    },
    'su-extra': (f) => { const k = $('#su-extra', f).value.trim().toLowerCase(); if (k && !S.e.extra.includes(k)) S.e.extra.push(k); seiteZeichnen(true); },
  };

  function verdrahten() {
    document.addEventListener('click', (ev) => {
      const el = ev.target.closest('[data-tun]');
      if (!el || el.disabled || el.getAttribute('aria-disabled') === 'true') return;
      const fn = AKTIONEN[el.dataset.tun];
      if (fn) { ev.preventDefault(); fn(el, ev); }
    });
    document.addEventListener('submit', (ev) => {
      const f = ev.target.closest('[data-form]');
      if (!f) return;
      ev.preventDefault();
      const fn = FORMULARE[f.dataset.form];
      if (fn) fn(f);
    });
    document.addEventListener('change', async (ev) => {
      const el = ev.target;
      if (el.matches('[data-umsortieren]') && el.value) {
        try {
          const r = await tun('zuordnen', { id: el.dataset.umsortieren, kategorie: el.value, quelle: 'assign' });
          hinweis({ titel: t('web.toast.moved', { datei: r.datei, neu: r.neu.name }), text: t('web.review.learns'), art: 'erfolg' });
          feiern({ spiel: r.spiel });
        } catch (e) { fehler(e); }
        await zustandLaden(); rahmenZeichnen(); seiteZeichnen(true);
      }
      if (el.matches('[data-modus]')) {
        try { await tun('modus', { name: el.value }); await zustandLaden(); rahmenZeichnen(); } catch (e) { fehler(e); }
        seiteZeichnen(true);
      }
    });
    $('#projekt-wahl').addEventListener('change', (ev) => {
      const v = ev.target.value;
      if (v === '__neu') { S.e = neueEinrichtung(); location.hash = '#/einrichten'; seiteZeichnen(true); return; }
      if (v) AKTIONEN.wechseln({ dataset: { pfad: v } });
    });
    $('#rueckflug').addEventListener('click', (ev) => AKTIONEN.rueckflug(ev.currentTarget));
    const umschalten = (offen) => {
      $('#protokoll').hidden = !offen;
      $('#protokoll-knopf').setAttribute('aria-expanded', String(offen));
      if (offen) { protokollZeichnen(); $('#protokoll-zu').focus(); } else $('#protokoll-knopf').focus();
    };
    $('#protokoll-knopf').addEventListener('click', () => umschalten($('#protokoll').hidden));
    $('#protokoll-zu').addEventListener('click', () => umschalten(false));

    // Ziehen & Ablegen: Eintrag auf eine Wabe ziehen = zuordnen (das Gedächtnis lernt).
    document.addEventListener('dragstart', (ev) => {
      const tr = ev.target.closest && ev.target.closest('tr[data-id]');
      if (tr) { ev.dataTransfer.setData('text/plain', tr.dataset.id); ev.dataTransfer.effectAllowed = 'move'; }
    });
    document.addEventListener('dragover', (ev) => {
      const k = ev.target.closest && ev.target.closest('.wabe-kachel');
      if (k) { ev.preventDefault(); $$('.wabe-kachel.ziel').forEach((x) => x !== k && x.classList.remove('ziel')); k.classList.add('ziel'); }
    });
    document.addEventListener('dragleave', (ev) => {
      const k = ev.target.closest && ev.target.closest('.wabe-kachel');
      if (k && !k.contains(ev.relatedTarget)) k.classList.remove('ziel');
    });
    document.addEventListener('drop', async (ev) => {
      const k = ev.target.closest && ev.target.closest('.wabe-kachel');
      if (!k) return;
      ev.preventDefault();
      k.classList.remove('ziel');
      const id = ev.dataTransfer.getData('text/plain');
      if (!id) return;
      try {
        const r = await tun('zuordnen', { id, kategorie: k.dataset.wabe, quelle: 'assign' });
        hinweis({ titel: t('web.toast.moved', { datei: r.datei, neu: r.neu.name }), text: t('web.review.learns'), art: 'erfolg' });
        feiern({ spiel: r.spiel });
      } catch (e) { fehler(e); }
      await zustandLaden(); rahmenZeichnen(); seiteZeichnen(true);
    });

    // Tastatur — dieselben Kürzel wie in der Konsole.
    document.addEventListener('keydown', (ev) => {
      if (ev.ctrlKey || ev.metaKey || ev.altKey) return;
      if (ev.target.closest('input, textarea, select, [contenteditable], dialog')) return;
      if (ev.key === 'Escape' && !$('#protokoll').hidden) { $('#protokoll-zu').click(); return; }
      const r = S.route[0];
      if (r === 'rueckfragen' && S.rueck.faelle.length) {
        if (/^[1-9]$/.test(ev.key)) { const w = S.rueck.waben[Number(ev.key) - 1]; if (w) { ev.preventDefault(); rueckAntwort(w.key); } return; }
        if (ev.key === 'Enter' && !ev.target.closest('button, a')) { ev.preventDefault(); AKTIONEN['rueck-ok'](); return; }
        if (ev.key === 's' || ev.key === 'ArrowRight') { ev.preventDefault(); rueckWeiter(); return; }
        if (ev.key === 'v') { ev.preventDefault(); AKTIONEN['rueck-oeffnen'](); return; }
      }
      if (r === 'flugloch' && !S.lauf && projekt() && projekt().lose) {
        if (ev.key === 'v') { ev.preventDefault(); vorschauStarten(); return; }
        if (ev.key === 's') { ev.preventDefault(); sortierenStarten(false); return; }
      }
      const ziel = { h: 'zuhause', f: 'flugloch', r: 'rueckfragen', w: 'waben' }[ev.key];
      if (ziel) location.hash = '#/' + ziel;
    });

    window.addEventListener('hashchange', navigieren);
    window.addEventListener('resize', kopfMessen);
    // Automatik-Thema: jede Minute nachsehen, ob es Abend geworden ist.
    setInterval(() => { if (einst().thema === 'auto') einstellungenAnwenden(); }, 60000);
  }

  // ------------------------------------------------------------------ //
  //  Start
  // ------------------------------------------------------------------ //
  async function start() {
    try {
      const texte = await lesen('texte');
      T = texte.texte;
      await zustandLaden();
      const log = await lesen('protokoll');
      S.ereignisse = log.ereignisse.filter((e) => e.text);
    } catch (e) {
      // Ohne gültiges Token gibt es auch keine Texte — daher hier fest zweisprachig.
      const text = e.status === 401
        ? 'Diese Sitzung ist abgelaufen oder die Adresse unvollständig. Bitte die Adresse aus der Konsole neu öffnen (pollysort-web). · This session has expired or the address is incomplete. Please open the address from the console again.'
        : e.message;
      $('#inhalt').innerHTML = `<div class="seite"><section class="karte leer-zustand">${P.sprite('frage')}<p>${esc(text)}</p></section></div>`;
      return;
    }
    verdrahten();
    stromVerbinden();
    await navigieren();
  }

  start();
})();
