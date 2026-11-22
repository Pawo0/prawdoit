// Every word shown in the video, in one place. The interface in the footage is Polish, so the captions are too.
const seconds = (s: number) => (s < 10 ? s.toFixed(1).replace('.', ',') : String(Math.round(s)));

export const COPY = {
  brand: 'PRAWDOWID',
  intro: {
    lead: 'Sprawdź wiadomość, zanim ją udostępnisz.',
    sub: 'Jeden silnik weryfikacji — trzy miejsca, w których go spotkasz.',
    channels: ['Strona WWW', 'Discord', 'Wtyczka przeglądarki'],
  },
  skipped: (s: number) => `>> pominięto ${seconds(s)} s oczekiwania`,
  web: {
    tag: '1/3 · Strona WWW',
    card: {no: '01', title: 'Strona WWW', sub: 'Wklejasz tekst lub link. Dostajesz ocenę i źródła.'},
    window: 'Prawdowid — strona WWW',
    paste: 'Wklejasz wiadomość, którą chcesz sprawdzić.',
    search: 'Silnik szuka dowodów w katalogu źródeł.',
    verdict: 'Werdykt z uzasadnieniem — nie sama etykieta.',
    source: 'Główne źródło: kto, kiedy, link do publikacji.',
    quote: 'Dowód to dosłowny cytat ze źródła.',
    second: 'A jeśli o sprawie nikt jeszcze nie pisał?',
    live: 'Przeszukiwane są też zaufane strony — na żywo.',
    abstain: 'Brak dowodów: Prawdowid nie zgaduje.',
    settle: 'Mówi, czego nie ustalono i co by to rozstrzygnęło.',
  },
  discord: {
    tag: '2/3 · Discord',
    card: {no: '02', title: 'Discord', sub: 'Ten sam silnik jako bot: komenda /sprawdz.'},
    window: 'Discord — prawdziwy serwer, prawdziwy bot',
    channel: 'Bot działa na serwerze — w kanale i w wiadomości prywatnej.',
    command: 'Komenda /sprawdz przyjmuje tekst albo link.',
    send: 'Enter — i pytanie trafia do tego samego silnika.',
    reply: (s: number) => `Odpowiedź po ${seconds(s)} s: werdykt i źródła z cytatami.`,
    link: 'Linki prowadzą do publikacji i do pełnej analizy.',
  },
  extension: {
    tag: '3/3 · Wtyczka',
    card: {no: '03', title: 'Wtyczka', sub: 'Oceny fact-checkerów przy treściach, które czytasz.'},
    window: 'Wtyczka Prawdowid — strona demonstracyjna',
    scan: 'Wtyczka porównuje posty z ocenionymi już informacjami.',
    badge: 'Oznaczenie zawsze podaje źródło, ocenę i datę.',
    neutral: 'Zwykłe posty zostają bez oznaczeń.',
    more: 'Kolejne oznaczenia pojawiają się podczas przewijania.',
    fab: 'Lupka: wskazujesz dowolny fragment strony.',
    pick: 'Jedno kliknięcie uruchamia pełne sprawdzenie.',
    sheet: 'Wynik w okienku — bez opuszczania strony.',
    details: 'Uzasadnienie i cytaty: jedno kliknięcie dalej.',
  },
  outro: {
    title: 'Zawsze ze źródłem.',
    title2: 'Bez zgadywania.',
    rows: [
      ['Strona WWW', 'werdykt, cytaty, przebieg sprawdzenia'],
      ['Discord', 'komenda /sprawdz, wzmianka, wiadomość prywatna'],
      ['Wtyczka', 'oceny przy postach i sprawdzanie fragmentu'],
    ],
    note: 'Nagranie działającej aplikacji. Odpowiedzi są prawdziwe; czas oczekiwania skrócono tylko tam, gdzie to zaznaczono.',
  },
};
